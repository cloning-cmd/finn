"""Results enrichment: every number on a results card comes from the NSE XBRL filing, never from a model.

Current quarter  = XBRL of the filing (NSE "integrated filing" endpoint, post Dec-2024; legacy endpoint before).
Comparatives     = XBRL of the previous quarter and the same quarter last year (same basis), fetched from the same index.
Three NSE formats are handled: Ind-AS corporate, banking (Schedule III bank format) and NBFC Ind-AS.
EBITDA is computed as PBT + finance costs + D&A - other income (method recorded on the card).
XBRL files are cached on disk by URL; a filing's XBRL never changes (revisions get a new URL).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Optional

from lxml import etree
from sqlalchemy import select

from api import db
from api.config import settings
from api.ingest.documents import url_key
from api.ingest.nse import NSEClient
from api.models import MarginRow, MetricRow, ResultsPayload
from api.pipeline.classify import clean_subject
from api.pipeline.score import fiscal_label, headline_for, period_from_text

log = logging.getLogger(__name__)
XBRL_DIR = settings.data_path / "xbrl"
XBRL_DIR.mkdir(parents=True, exist_ok=True)
CR = 1e7  # XBRL values are in rupees; cards are in Rs Cr

# ----------------------------------------------------------------------------- index of results filings per symbol


def _d(s: str, fmt: str) -> Optional[dt.date]:
    try:
        return dt.datetime.strptime(s.strip(), fmt).date()
    except (ValueError, AttributeError):
        return None


def results_index(symbol: str, client: NSEClient) -> list[dict]:
    """All quarterly results filings with an XBRL link: [{qe, basis, url, audited, filed, src}] newest first."""
    out: list[dict] = []
    try:
        d = client.get_json("/api/integrated-filing-results", {"index": "equities", "symbol": symbol, "period": "Quarterly", "size": 100})
        for r in (d.get("data", []) if isinstance(d, dict) else []):
            if "Financial" not in (r.get("type") or "") or not r.get("xbrl"):
                continue
            qe = _d(r.get("qe_Date") or "", "%d-%b-%Y")
            if qe:
                out.append({"qe": qe, "basis": "consolidated" if (r.get("consolidated") or "").lower().startswith("cons") else "standalone",
                            "url": r["xbrl"], "audited": r.get("audited"), "filed": r.get("broadcast_Date") or r.get("creation_Date"),
                            "src": "integrated"})
    except Exception as e:  # NSE blocked / shape change: fall through to legacy
        log.warning("integrated-filing index failed for %s: %s", symbol, e)
    try:
        for r in client.financial_results(symbol) or []:
            if not r.get("xbrl") or r.get("period") not in (None, "Quarterly"):
                continue
            qe = _d(r.get("toDate") or "", "%d-%b-%Y")
            if qe:
                out.append({"qe": qe, "basis": "consolidated" if (r.get("consolidated") or "") == "Consolidated" else "standalone",
                            "url": r["xbrl"], "audited": r.get("audited"), "filed": r.get("broadcastDate"), "src": "legacy"})
    except Exception as e:
        log.warning("legacy results index failed for %s: %s", symbol, e)
    seen: set[tuple] = set()
    uniq = []
    for r in sorted(out, key=lambda r: (r["qe"], r["src"] == "integrated", r["filed"] or ""), reverse=True):
        k = (r["qe"], r["basis"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def fetch_xbrl(url: str, client: Optional[NSEClient] = None) -> Optional[bytes]:
    p = XBRL_DIR / f"{url_key(url)}.xml"
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes()
    client = client or NSEClient()
    try:
        r = client.c.get(url)
    except Exception as e:
        log.info("xbrl fetch error %s: %s", url[-60:], e)
        return None
    if r.status_code != 200 or not r.content.lstrip().startswith(b"<"):
        log.info("xbrl fetch %s -> %s", url[-60:], r.status_code)
        return None
    p.write_bytes(r.content)
    return r.content


# ----------------------------------------------------------------------------- parsing


def parse_quarter(raw: bytes) -> dict:
    """Facts for the current quarter (context OneD) in Rs Cr, plus period dates, basis and format."""
    root = etree.fromstring(raw, parser=etree.XMLParser(huge_tree=True, recover=True))
    periods: dict[str, tuple] = {}
    for ctx in root.iter("{*}context"):
        per = ctx.find("{*}period")
        if per is None:
            continue
        vals = {etree.QName(x).localname: (x.text or "").strip() for x in per}
        periods[ctx.get("id")] = (vals.get("startDate"), vals.get("endDate") or vals.get("instant"))
    v: dict[str, float] = {}
    text: dict[str, str] = {}
    for el in root.iter():
        if el.get("contextRef") != "OneD" or el.text is None:
            continue
        tag = etree.QName(el).localname
        t = el.text.strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", t):
            v[tag] = float(t)
        else:
            text[tag] = t[:80]
    start, end = periods.get("OneD", (None, None))
    fmt = "banking" if "InterestEarned" in v and "InterestExpended" in v else "nbfc" if "ImpairmentOnFinancialInstruments" in v else "indas"
    basis_txt = (text.get("NatureOfReportStandaloneConsolidated") or "").lower()
    return {"start": _d(start or "", "%Y-%m-%d"), "end": _d(end or "", "%Y-%m-%d"), "format": fmt,
            "basis": "consolidated" if basis_txt.startswith("cons") else "standalone" if basis_txt else None,
            "v": {k: x / CR for k, x in v.items()}, "text": text}


def _first(v: dict, *tags: str) -> Optional[float]:
    for t in tags:
        if t in v:
            return v[t]
    return None


def compute_metrics(facts: dict) -> tuple[dict[str, float], Optional[str], list[str]]:
    """Return ({metric: Rs Cr}, ebitda_method, gaps). Arithmetic only; every input is an XBRL tag."""
    v, fmt, gaps = facts["v"], facts["format"], []
    m: dict[str, float] = {}
    method = None
    if fmt == "banking":
        ie, ix = _first(v, "InterestEarned"), _first(v, "InterestExpended")
        if ie is not None and ix is not None:
            m["NII"] = ie - ix
        ppop = _first(v, "OperatingProfitBeforeProvisionAndContingencies")
        if ppop is not None:
            m["PPOP"] = ppop
        prov = _first(v, "ProvisionsOtherThanTaxAndContingencies")
        if prov is not None:
            m["Provisions"] = prov
        pat = _first(v, "ProfitLossForThePeriod", "ProfitLossFromOrdinaryActivitiesAfterTax",
                     "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates")
        if pat is not None:
            m["PAT"] = pat
    elif fmt == "nbfc":
        ie, fc = _first(v, "InterestEarned", "InterestIncome"), _first(v, "FinanceCosts")
        if ie is not None and fc is not None:
            m["NII"] = ie - fc
        pbt = _first(v, "ProfitBeforeTax", "ProfitBeforeExceptionalItemsAndTax")
        imp = _first(v, "ImpairmentOnFinancialInstruments")
        if pbt is not None and imp is not None:
            m["PPOP"] = pbt + imp
            m["Provisions"] = imp
        pat = _first(v, "ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations")
        if pat is not None:
            m["PAT"] = pat
    else:
        rev = _first(v, "RevenueFromOperations", "Revenue")
        if rev is not None:
            m["Revenue"] = rev
        pbt = _first(v, "ProfitBeforeTax", "ProfitBeforeExceptionalItemsAndTax")
        fc, da, oi = _first(v, "FinanceCosts"), _first(v, "DepreciationDepletionAndAmortisationExpense"), _first(v, "OtherIncome")
        if pbt is not None and fc is not None and da is not None:
            if oi is None:
                inc = _first(v, "Income")
                oi = (inc - rev) if (inc is not None and rev is not None) else None
            if oi is not None:
                m["EBITDA"] = pbt + fc + da - oi
                method = "computed_excl_other_income"
            else:
                m["EBITDA"] = pbt + fc + da
                method = "computed_incl_other_income"
        if pbt is not None:
            m["PBT"] = pbt
        pat = _first(v, "ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations", "ProfitLossForThePeriod")
        if pat is not None:
            m["PAT"] = pat
    order = ["NII", "PPOP", "Provisions", "PAT"] if fmt in ("banking", "nbfc") else ["Revenue", "EBITDA", "PBT", "PAT"]
    gaps.extend(f"{k} missing in XBRL" for k in order if k not in m)
    return {k: round(m[k], 2) for k in order if k in m}, method, gaps


def pct(cur: float, prev: Optional[float]) -> float:
    if prev is None or prev == 0:
        return 0.0
    return round((cur - prev) / abs(prev) * 100, 1)


def period_label(end: dt.date) -> str:
    start = end.replace(day=1)
    for _ in range(2):
        start = (start - dt.timedelta(days=1)).replace(day=1)
    return f"{fiscal_label(end)} ({start:%b}-{end:%b} {end.year})"


def build_payload(cur: dict, prev_q: Optional[dict], prev_y: Optional[dict], basis: str) -> tuple[ResultsPayload, list[str]]:
    mc, method, gaps = compute_metrics(cur)
    mq = compute_metrics(prev_q)[0] if prev_q else {}
    my = compute_metrics(prev_y)[0] if prev_y else {}
    if not prev_q:
        gaps.append("no previous-quarter XBRL (QoQ shown as 0)")
    if not prev_y:
        gaps.append("no year-ago XBRL (YoY shown as 0)")
    rows = [MetricRow(name=k, value=x, prev_q=mq.get(k, 0.0), prev_y=my.get(k, 0.0), qoq_pct=pct(x, mq.get(k)), yoy_pct=pct(x, my.get(k)))
            for k, x in mc.items()]
    margins = None
    if cur["format"] == "indas" and mc.get("Revenue"):
        def margin(d: dict, k: str) -> Optional[float]:
            return (d[k] / d["Revenue"] * 100) if d.get("Revenue") and k in d else None
        margins = []
        for k, name in (("EBITDA", "EBITDA margin"), ("PAT", "PAT margin")):
            now = margin(mc, k)
            if now is None:
                continue
            q, y = margin(mq, k), margin(my, k)
            margins.append(MarginRow(name=name, pct=round(now, 1), qoq_bps=int(round((now - q) * 100)) if q is not None else 0,
                                     yoy_bps=int(round((now - y) * 100)) if y is not None else 0))
    payload = ResultsPayload(period=period_label(cur["end"]), basis=basis, variant="lender" if cur["format"] != "indas" else "standard",
                             metrics=rows, margins=margins or None, ebitda_method=method, extraction="xbrl")
    return payload, gaps


# ----------------------------------------------------------------------------- copy (numbers only, deterministic)


def inr(x: float) -> str:
    """Indian grouping: 129359 -> 1,29,359."""
    n = int(round(abs(x)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join(re.findall(r"\d{1,2}(?=(?:\d{2})*$)", head))
        s = f"{head},{tail}"
    return f"-{s}" if x < 0 else s


def signed(p: float) -> str:
    return f"{p:+.1f}%"


def headline_from_payload(ticker: str, p: ResultsPayload, quarter_end: dt.date) -> str:
    by = {m.name: m for m in p.metrics}
    top = by.get("Revenue") or by.get("NII")
    pat = by.get("PAT")
    q = fiscal_label(quarter_end)
    tname = "rev" if "Revenue" in by else "NII"
    if pat and pat.value < 0:  # a loss: percentages against a negative base mislead, state both amounts instead
        loss, prev = inr(abs(pat.value)), inr(abs(pat.prev_y))
        was = f" (vs ₹{prev} Cr loss)" if pat.prev_y < 0 else f" (profit ₹{prev} Cr yr ago)" if pat.prev_y > 0 else ""
        cands = ([f"{ticker} {q}: {tname} ₹{inr(top.value)} Cr {signed(top.yoy_pct)} YoY, loss ₹{loss} Cr{was}"] if top else []) + \
                [f"{ticker} {q}: {tname} {signed(top.yoy_pct)} YoY, loss ₹{loss} Cr{was}" if top else "",
                 f"{ticker} {q}: loss ₹{loss} Cr{was}", f"{ticker} {q}: loss ₹{loss} Cr"]
        return next(h for h in cands if h and len(h) <= 70)
    if top and pat:
        for h in (f"{ticker} {q}: {tname} ₹{inr(top.value)} Cr {signed(top.yoy_pct)} YoY, PAT ₹{inr(pat.value)} Cr {signed(pat.yoy_pct)}",
                  f"{ticker} {q}: {tname} {signed(top.yoy_pct)} YoY, PAT {signed(pat.yoy_pct)} YoY",
                  f"{ticker} {q}: PAT ₹{inr(pat.value)} Cr {signed(pat.yoy_pct)} YoY"):
            if len(h) <= 70:
                return h
    if pat:
        return f"{ticker} {q}: PAT ₹{inr(pat.value)} Cr"[:70]
    return f"{ticker} {q} results ({p.basis})"[:70]


def one_liner_from_payload(p: ResultsPayload) -> Optional[str]:
    by = {m.name: m for m in p.metrics}
    bits = []
    if p.margins:
        m = p.margins[0]
        bits.append(f"{m.name} {m.pct:.1f}% ({m.qoq_bps:+d} bps QoQ, {m.yoy_bps:+d} bps YoY)")
    for k in ("EBITDA", "PPOP", "Provisions"):
        if k in by:
            bits.append(f"{k} ₹{inr(by[k].value)} Cr {signed(by[k].qoq_pct)} QoQ")
            break
    if not bits:
        return None
    s = "; ".join(bits) + f". {p.basis.capitalize()}, from XBRL."
    return s[:140]


# ----------------------------------------------------------------------------- orchestration


def _quarter_end_for(f: db.Filing) -> Optional[dt.date]:
    d = period_from_text(f.subject or "") or period_from_text((f.body_text or "")[:4000])
    if d:
        return d
    ts = f.ts.date()  # fall back: latest quarter end before the filing
    cands = [dt.date(ts.year, m, dd) for m, dd in ((3, 31), (6, 30), (9, 30), (12, 31))] + [dt.date(ts.year - 1, 12, 31)]
    past = [c for c in cands if c < ts]
    return max(past) if past else None


def _prev_quarter_end(qe: dt.date) -> dt.date:
    d = qe.replace(day=1)
    for _ in range(3):
        d = (d - dt.timedelta(days=1)).replace(day=1)
    nxt = (d + dt.timedelta(days=32)).replace(day=1)
    return nxt - dt.timedelta(days=1)


MAX_FILED_GAP_DAYS = 2


def _filed_date(r: dict) -> Optional[dt.date]:
    s = (r.get("filed") or "").strip()
    return _d(s[:11], "%d-%b-%Y") or _d(s[:10], "%Y-%m-%d")


def _filed_within(r: dict, ts: dt.datetime, days: int) -> bool:
    fd = _filed_date(r)
    if fd is None:
        return True  # index row without a date: do not block on it
    return abs((fd - ts.date()).days) <= days


def _year_ago(qe: dt.date) -> dt.date:
    try:
        return qe.replace(year=qe.year - 1)
    except ValueError:
        return qe.replace(year=qe.year - 1, day=28)


def enrich_filing(f: db.Filing, index: list[dict], client: NSEClient) -> Optional[dict]:
    qe = _quarter_end_for(f)
    if not qe:
        return None
    rows = [r for r in index if r["qe"] == qe]
    if not rows:
        return {"gaps": [f"no XBRL in NSE results index for quarter ended {qe}"]}
    # The XBRL is broadcast the same day as the results filing (next morning at the latest). A results-looking
    # filing whose XBRL arrived weeks later (board-meeting notice, listing update) must not get those numbers.
    near = [r for r in rows if _filed_within(r, f.ts, MAX_FILED_GAP_DAYS)]
    if not near:
        return {"gaps": [f"no XBRL filed within {MAX_FILED_GAP_DAYS} days of this filing (quarter ended {qe})"]}
    row = next((r for r in near if r["basis"] == "consolidated"), near[0])
    basis = row["basis"]

    def load(q: dt.date) -> Optional[dict]:
        r = next((r for r in index if r["qe"] == q and r["basis"] == basis), None)
        raw = fetch_xbrl(r["url"], client) if r else None
        return parse_quarter(raw) if raw else None

    cur = load(qe)
    if not cur or not cur["v"]:
        return {"gaps": [f"XBRL for {qe} could not be fetched/parsed"]}
    payload, gaps = build_payload(cur, load(_prev_quarter_end(qe)), load(_year_ago(qe)), basis)
    return {"payload": payload, "gaps": gaps, "quarter_end": qe, "xbrl_url": row["url"], "format": cur["format"], "basis": basis}


def enrich_results(tickers: Optional[list[str]] = None, force: bool = False, client: Optional[NSEClient] = None) -> dict:
    """Attach ResultsPayload + numeric headline to every primary results filing lacking one. One index call per ticker."""
    client = client or NSEClient()
    done, skipped, failed = 0, 0, 0
    with db.session() as s:
        q = select(db.Filing).where(db.Filing.category == "results", db.Filing.tier.is_not(None)).order_by(db.Filing.ticker, db.Filing.ts.desc())
        if tickers:
            q = q.where(db.Filing.ticker.in_(tickers))
        filings = s.scalars(q).all()
        index_cache: dict[str, list[dict]] = {}
        for f in filings:
            p = dict(f.payload or {})
            if p.get("collapsed_into"):
                continue  # the primary filing of the event carries the card
            if not force and (p.get("payload") or {}).get("extraction") == "xbrl":
                skipped += 1
                continue
            if f.ticker not in index_cache:
                index_cache[f.ticker] = results_index(f.ticker, client)
            try:
                res = enrich_filing(f, index_cache[f.ticker], client)
            except Exception as e:
                log.exception("enrich failed for %s", f.id)
                res = {"gaps": [f"enrich error: {e}"]}
            if not res or "payload" not in res:
                p["results"] = {"gaps": (res or {}).get("gaps", ["no quarter end found"])}
                if (p.get("payload") or {}).get("extraction") == "xbrl":  # stale numbers from an earlier run: revert
                    p["payload"] = {"summary": clean_subject(f.ticker, f.subject or "")}
                    p["sources"] = [x for x in p.get("sources", []) if not x["id"].startswith("s_x_")]
                    p["chips"] = [c for c in p.get("chips", []) if c.get("label") != "Open XBRL"]
                    f.headline = headline_for(f.ticker, f.subject or "", "results", f.body_text or "")
                    f.one_liner = None
                f.payload = p
                failed += 1
                continue
            rp: ResultsPayload = res["payload"]
            p["payload"] = rp.model_dump()
            p["results"] = {"gaps": res["gaps"], "quarter_end": res["quarter_end"].isoformat(), "format": res["format"], "xbrl_url": res["xbrl_url"]}
            src = {"id": f"s_x_{f.id[-12:]}", "label": "Results XBRL (NSE)", "url": res["xbrl_url"]}
            p["sources"] = [src] + [x for x in p.get("sources", []) if x.get("id") != src["id"]]
            chips = [c for c in p.get("chips", []) if c.get("label") != "Open XBRL"]
            p["chips"] = [{"label": "Open XBRL", "action": "open_source", "arg": src["id"]}] + chips
            f.payload = p
            f.headline = headline_from_payload(f.ticker, rp, res["quarter_end"])
            f.one_liner = one_liner_from_payload(rp)
            done += 1
    return {"enriched": done, "skipped": skipped, "failed": failed}
