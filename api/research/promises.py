"""Promise Ledger. Extraction (cheap model, 5 chunks per call, exact quotes verified against the chunk) →
matching (code only: hard promises vs screener quarterly/annual actuals) → later mentions (embedding + keyword
search in subsequent calls; absent in the next 2 calls → quietly_dropped).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from api.llm import router
from api.models import LaterMention, PromiseRec, Source
from api.research import docs
from api.research.verify import numbers_in, quote_in_text

log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "extract_guidance.md"
BATCH = 5
FORWARD = re.compile(r"guidance|guide|expect|target|aim|outlook|we plan|will be|going forward|next (?:year|quarter|few)|FY\s?\d{2}|by (?:the )?end|"
                     r"over the (?:next|coming)|medium term|long term|trajectory|commit|should (?:be|see|reach)|on track|deliver|capex|margin band", re.I)
MONTHS ={m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
METRIC_WORDS = {
    "revenue_growth": ["revenue", "growth", "guidance", "constant currency"], "ebitda_margin": ["margin", "ebitda", "operating margin"],
    "pat": ["profit", "pat", "net income"], "capex": ["capex", "capital expenditure", "investment"], "net_debt": ["debt", "leverage", "deleverag"],
    "order_book": ["order", "deal", "tcv", "book"], "capacity": ["capacity", "mw", "plant", "expansion"], "launch": ["launch", "go live", "roll out"],
    "headcount": ["headcount", "hiring", "employees"], "other": [],
}


class PromiseDraft(BaseModel):
    chunk_id: str
    metric: str = "other"
    target_text: str
    target_low: Optional[float] = None
    target_high: Optional[float] = None
    unit: Optional[str] = None
    period: str = "unspecified"
    speaker: Optional[str] = None
    quote: str
    hard: bool = False


class GuidanceOut(BaseModel):
    promises: list[PromiseDraft] = Field(default_factory=list)


def period_date(label: str) -> dt.date:
    """'Oct 2026' → 2026-10-01 (concall label)."""
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})", label or "")
    return dt.date(int(m.group(2)), MONTHS.get(m.group(1), 1), 1) if m else dt.date(1900, 1, 1)


# ----------------------------------------------------------------------------- extraction


def _render(chunks: list[dict]) -> str:
    tpl = PROMPT_PATH.read_text(encoding="utf-8")
    body = "\n\n".join(f"[chunk_id={c['id']}] [call={c['period']}] [speaker={c['speaker']}]\n{c['text']}" for c in chunks)
    return tpl.replace("{{chunks}}", body)


def extract_promises(ticker: str, chunks: list[dict], progress=None) -> tuple[list[PromiseRec], dict, list[str]]:
    """Management chunks of concalls → PromiseRec drafts with verified quotes. Returns (promises, cost, gaps)."""
    by_id = {c["id"]: c for c in chunks}
    out: list[PromiseRec] = []
    cost = {"inr": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0, "cached": 0, "models": set()}
    gaps: list[str] = []
    seen_quotes: set[str] = set()
    candidates = [c for c in chunks if FORWARD.search(c["text"])]  # cheap prefilter: forward-looking language only
    batches = [candidates[i:i + BATCH] for i in range(0, len(candidates), BATCH)]
    for bi, batch in enumerate(batches):
        if progress and bi % 5 == 0:
            progress("guidance", "start", f"batch {bi + 1}/{len(batches)}")
        try:
            res, meta = router.call("guidance_extract", PROMPT_VERSION, _render(batch), GuidanceOut, max_tokens=1500)
        except router.LLMUnavailable as e:
            gaps.append(f"guidance extraction unavailable: {e}")
            break
        cost["inr"] += meta["cost_inr"]
        cost["tokens_in"] += meta["tokens_in"]
        cost["tokens_out"] += meta["tokens_out"]
        cost["calls"] += 1
        cost["cached"] += int(meta["cached"])
        cost["models"].add(meta["model"])
        for d in res.promises:
            c = by_id.get(d.chunk_id)
            if c is None or not quote_in_text(d.quote, c["text"]):
                continue  # fabricated or paraphrased quote → dropped
            key = re.sub(r"\W+", " ", d.quote.lower()).strip()[:80]
            if key in seen_quotes:
                continue
            seen_quotes.add(key)
            pid = f"p_{ticker}_{hashlib.sha256((c['id'] + d.quote).encode()).hexdigest()[:8]}"
            out.append(PromiseRec(
                id=pid, ticker=ticker, metric=(d.metric or "other").lower().replace(" ", "_"), target_text=d.target_text[:200],
                target_low=d.target_low, target_high=d.target_high, unit=d.unit, period=d.period or "unspecified",
                said_in=c["period"], speaker=(d.speaker or (c["speaker"] or "").replace(" [mgmt]", "")) or None, quote=d.quote[:600],
                source=Source(id=c["id"], label=f"Concall {c['period']}", url=c["url"], page=c["page"], quote=d.quote[:300]),
                status="too_early", hard=bool(d.hard and (d.target_low is not None or d.target_high is not None))))
    cost["models"] = sorted(cost["models"])
    return out, cost, gaps


# ----------------------------------------------------------------------------- matching (code only)


def _fy_of_quarter_label(q: str) -> Optional[str]:
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})", q)
    if not m:
        return None
    mon, yr = MONTHS[m.group(1)], int(m.group(2))
    fy = yr + 1 if mon >= 4 else yr
    return f"FY{fy % 100:02d}"


def _target_quarters(period: str) -> tuple[Optional[str], list[str]]:
    """('FY27', ['Jun 2026', 'Sep 2026', 'Dec 2026', 'Mar 2027']) for the promise period, quarter subset for Qn/Hn."""
    m = re.search(r"FY\s?(\d{2,4})", period or "", re.I)
    if not m:
        return None, []
    fy = int(m.group(1)) % 100
    yr = 2000 + fy
    quarters = [f"Jun {yr - 1}", f"Sep {yr - 1}", f"Dec {yr - 1}", f"Mar {yr}"]
    q = re.search(r"Q([1-4])", period, re.I)
    h = re.search(r"H([12])", period, re.I)
    if q:
        quarters = [quarters[int(q.group(1)) - 1]]
    elif h:
        quarters = quarters[:2] if h.group(1) == "1" else quarters[2:]
    return f"FY{fy:02d}", quarters


def _status_vs_band(actual: float, low: Optional[float], high: Optional[float], complete: bool, tol: float) -> str:
    lo = low if low is not None else high
    hi = high if high is not None else low
    if lo is None:
        return "too_early"
    if actual >= lo - tol:
        return "kept" if complete else "on_track"
    return "missed"


def match_hard(promises: list[PromiseRec], quarterly: dict[str, dict], annual: dict[str, dict], today: Optional[dt.date] = None) -> None:
    """Fill actual_text/actual_value/status for hard promises using screener actuals. Mutates in place."""
    for p in promises:
        if not p.hard:
            continue
        fy, quarters = _target_quarters(p.period)
        if not fy:
            continue
        have = [q for q in quarters if q in quarterly]
        complete = len(have) == len(quarters) and bool(have)
        if p.metric in ("revenue_growth", "sales_growth") and (p.unit or "pct") == "pct":
            if complete and len(quarters) == 4 and fy in annual and annual[fy].get("yoy_sales_pct") is not None:
                actual = annual[fy]["yoy_sales_pct"]
                p.actual_text = f"{fy} revenue growth {actual:+.0f}% (reported)"
            elif have:
                vals = [quarterly[q].get("yoy_sales_pct") for q in have if quarterly[q].get("yoy_sales_pct") is not None]
                if not vals:
                    continue
                actual = sum(vals) / len(vals)
                p.actual_text = f"{', '.join(have)} YoY sales growth avg {actual:+.1f}% (reported)"
            else:
                continue
            p.actual_value = round(actual, 1)
            p.status = _status_vs_band(actual, p.target_low, p.target_high, complete, tol=0.5)
            p.actual_source = Source(id="s_screener", label="screener.in quarterly table", url="https://www.screener.in/")
        elif p.metric in ("ebitda_margin", "operating_margin", "opm", "margin") and (p.unit or "pct") == "pct":
            vals = [quarterly[q].get("opm_pct") for q in have if quarterly[q].get("opm_pct") is not None]
            if not vals:
                continue
            actual = sum(vals) / len(vals)
            p.actual_value = round(actual, 1)
            p.actual_text = f"{', '.join(have)} OPM avg {actual:.1f}% (reported)"
            p.status = _status_vs_band(actual, p.target_low, p.target_high, complete, tol=1.0)
            p.actual_source = Source(id="s_screener", label="screener.in quarterly table", url="https://www.screener.in/")
        elif p.metric in ("revenue", "pat", "ebitda") and (p.unit or "") == "inr_cr":
            key = {"revenue": "revenue", "pat": "pat", "ebitda": "ebitda"}[p.metric]
            vals = [quarterly[q].get(key) for q in have if quarterly[q].get(key) is not None]
            if not vals:
                continue
            actual = sum(vals) if len(quarters) > 1 else vals[0]
            p.actual_value = round(actual, 0)
            p.actual_text = f"{p.metric.upper()} {actual:,.0f} Cr over {', '.join(have)}"
            p.status = _status_vs_band(actual, p.target_low, p.target_high, complete, tol=0.01 * actual)
            p.actual_source = Source(id="s_screener", label="screener.in quarterly table", url="https://www.screener.in/")
        # capex / net_debt / capacity: no screener actual → stays too_early; later mentions decide


# ----------------------------------------------------------------------------- later mentions


def later_mentions(ticker: str, promises: list[PromiseRec], call_periods: list[str]) -> None:
    """For each promise, look in each later call for the metric: reiterated / raised / lowered / absent."""
    ordered = sorted(set(call_periods), key=period_date)
    for p in promises:
        later = [c for c in ordered if period_date(c) > period_date(p.said_in)]
        mentions: list[LaterMention] = []
        for call in later:
            hits = docs.search_chunks(ticker, f"{p.metric.replace('_', ' ')} {p.target_text}", k=3, period=call, management_only=True)
            words = METRIC_WORDS.get(p.metric, []) or [p.metric.replace("_", " ")]
            hit = next((h for h in hits if h["score"] >= 0.72 and any(w in h["text"].lower() for w in words)), None)
            if hit is None:
                mentions.append(LaterMention(call=call, stance="absent"))
                continue
            stance = "reiterated"
            if p.hard and p.target_low is not None:
                nums = [n for n in numbers_in(hit["text"]) if 0 < abs(n) < 1e6]
                near = [n for n in nums if abs(n - p.target_low) <= max(abs(p.target_low) * 0.5, 3)]
                if near:
                    v = near[0]
                    hi = p.target_high if p.target_high is not None else p.target_low
                    stance = "raised" if v > hi + 1e-9 else "lowered" if v < p.target_low - 1e-9 else "reiterated"
            mentions.append(LaterMention(call=call, stance=stance))
        p.later_mentions = mentions
        if any(m.stance == "lowered" for m in mentions) and p.status in ("too_early", "on_track"):
            p.status = "revised_down"
        elif p.status == "too_early" and len(mentions) >= 2 and all(m.stance == "absent" for m in mentions[:2]):
            p.status = "quietly_dropped"
        elif p.status == "too_early" and mentions and all(m.stance in ("reiterated", "raised") for m in mentions):
            p.status = "on_track"


def summarize(promises: list[PromiseRec]) -> dict[str, int]:
    from api.models import PROMISE_STATUSES
    s = {k: 0 for k in PROMISE_STATUSES}
    for p in promises:
        s[p.status] = s.get(p.status, 0) + 1
    return s
