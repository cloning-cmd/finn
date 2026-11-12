"""Specific headlines for generic filings ("Disclosure under Regulation 30…", "Credit Rating", "Rumour Verification").

The cheap model writes a headline, a one-liner and one verbatim supporting sentence from the filing text. Code then
checks the sentence against the filing (rapidfuzz ≥ 85) and every number in the headline/one-liner against the
numbers in the text; anything that fails leaves the card exactly as the rule-based scorer wrote it. The supporting
sentence is attached to the filing source so the source sheet shows it. Results and management-change cards have
their own enrichers and are skipped here.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select

from api import db
from api.llm import router
from api.research.verify import number_supported, numbers_in, quote_in_text

log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "one_liner.md"
GENERIC = re.compile(r"disclosure under reg|regulation 30|credit rating|intimation under|^\w+: (?:announcement|updates?|general updates?|"
                     r"press release|clarification|outcome of board meeting)\b|rumour verification|rumor verification", re.I)
SKIP_CATEGORIES = {"results", "management_change", "investor_meetings", "unclassified"}
TEXT_LIMIT = 6000


class OneLinerOut(BaseModel):
    headline: str
    one_liner: str = ""
    quote: str = ""


def is_generic(headline: Optional[str]) -> bool:
    return bool(GENERIC.search(headline or ""))


def clean_line(s: str, limit: int) -> str:
    s = re.sub(r"\s+", " ", s or "").replace("!", ".").strip(" .")
    s = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", s).strip()
    if len(s) <= limit:
        return s
    cut = s[: limit - 1]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit // 2 else cut).rstrip(" ,;:-–") + "…"


def verify(out: OneLinerOut, text: str) -> Optional[str]:
    """None when the model output is supported by the filing; otherwise the reason it is rejected."""
    if len(out.headline.strip()) < 8:
        return "headline too short"
    if not quote_in_text(out.quote, text):
        return "supporting sentence not in filing"
    pool = numbers_in(text)
    for v in numbers_in(out.headline) + numbers_in(out.one_liner):
        if not number_supported(v, pool):
            return f"number {v:g} not in filing"
    return None


def apply(f: db.Filing, out: OneLinerOut, meta: dict) -> None:
    f.headline = f"{f.ticker}: {clean_line(out.headline, 68 - len(f.ticker))}"
    f.one_liner = clean_line(out.one_liner, 140) or None
    payload = dict(f.payload or {})
    srcs = [dict(s) for s in payload.get("sources", [])]
    if srcs:
        srcs[0]["quote"] = re.sub(r"\s+", " ", out.quote).strip()[:300]
        payload["sources"] = srcs
    payload["one_liner"] = {"extraction": "llm", "prompt": PROMPT_VERSION, "model": meta["model"], "cost_inr": meta["cost_inr"], "verified": True}
    f.payload = payload


def enrich_filing(f: db.Filing, company: str) -> dict:
    text = re.sub(r"[ \t]+", " ", f.body_text or "").strip()
    if len(text) < 120:
        return {"skipped": "no text"}
    prompt = (PROMPT_PATH.read_text(encoding="utf-8").replace("{{company}}", company).replace("{{ticker}}", f.ticker)
              .replace("{{category}}", f.category or "").replace("{{subject}}", (f.subject or "")[:300]).replace("{{text}}", text[:TEXT_LIMIT]))
    out, meta = router.call("one_liner", PROMPT_VERSION, prompt, OneLinerOut, max_tokens=300)
    why = verify(out, text)
    if why:
        payload = dict(f.payload or {})
        payload["one_liner"] = {"extraction": "llm", "prompt": PROMPT_VERSION, "verified": False, "reason": why, "cost_inr": meta["cost_inr"]}
        f.payload = payload
        return {"rejected": why, "cost": meta["cost_inr"]}
    apply(f, out, meta)
    return {"headline": f.headline, "cost": meta["cost_inr"], "cached": meta["cached"]}


def enrich_oneliners(days: int = 45, force: bool = False, limit: int = 40, tiers: tuple[str, ...] = ("lead", "line")) -> dict:
    """Rewrite generic headlines on lead/line cards from the last `days`. Idempotent; ₹ only for new filings."""
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    done = rejected = skipped = 0
    cost = 0.0
    with db.session() as s:
        names = {c.ticker: c.name for c in s.scalars(select(db.Company)).all()}
        rows = s.scalars(select(db.Filing).where(db.Filing.ts >= since, db.Filing.tier.in_(tiers)).order_by(db.Filing.ts.desc())).all()
        for f in rows:
            p = f.payload or {}
            if f.category in SKIP_CATEGORIES or p.get("collapsed_into") or not (is_generic(f.headline) or p.get("one_liner")):
                continue  # a card this enricher already rewrote is no longer generic, but FORCE must still reach it
            if not force and p.get("one_liner"):
                continue
            if done + rejected >= limit:
                break
            try:
                r = enrich_filing(f, names.get(f.ticker) or f.ticker)
            except router.LLMUnavailable as e:
                log.warning("one_liner: model unavailable: %s", e)
                return {"done": done, "rejected": rejected, "skipped": skipped, "cost_inr": round(cost, 3), "gap": str(e)}
            except Exception as e:  # noqa: BLE001 - one bad filing must not stop the run
                log.warning("one_liner: %s failed: %s", f.id, str(e)[:120])
                skipped += 1
                continue
            cost += r.get("cost", 0) or 0
            if "headline" in r:
                done += 1
            elif "rejected" in r:
                rejected += 1
            else:
                skipped += 1
    return {"done": done, "rejected": rejected, "skipped": skipped, "cost_inr": round(cost, 3)}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.WARNING)
    print(enrich_oneliners(force="--force" in sys.argv))
