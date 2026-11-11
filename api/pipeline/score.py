"""Priority scoring + tiering + deterministic headlines. All constants in scoring.yaml."""
from __future__ import annotations

import datetime as dt
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import func, select

from api import db
from api.pipeline.classify import clean_subject

log = logging.getLogger(__name__)
CFG_PATH = Path(__file__).with_name("scoring.yaml")


@lru_cache(maxsize=1)
def cfg() -> dict:
    return yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))


def tier_for(priority: float) -> str:
    t = cfg()["tiers"]
    return "lead" if priority >= t["lead"] else "line" if priority >= t["line"] else "buried"


def pos_weight_factor(weight_pct: float) -> float:
    p = cfg()["position"]
    return p["floor"] + p["slope"] * (weight_pct / 100.0)


def pref_factor(s, ticker: str, category: str) -> float:
    p = cfg()["pref"]
    less = s.scalar(select(func.count()).select_from(db.Feedback).where(db.Feedback.ticker == ticker, db.Feedback.category == category, db.Feedback.action == "less")) or 0
    noted = s.scalar(select(func.count()).select_from(db.Feedback).where(db.Feedback.ticker == ticker, db.Feedback.category == category, db.Feedback.action == "noted")) or 0
    f = (p["less_each"] ** less) * (p["noted_each"] ** noted)
    return max(p["min"], min(p["max"], f))


def surprise_factor(s, ticker: str, ts: dt.datetime, guidance_gap: bool = False) -> float:
    sp = cfg()["surprise"]
    f = 1.0
    day = ts.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    # filings after market close affect the next session
    look = [day.isoformat(), (day + dt.timedelta(days=1)).isoformat()] if ts.hour >= 15 else [day.isoformat()]
    z = s.scalar(select(func.max(func.abs(db.PriceEOD.z))).where(db.PriceEOD.ticker == ticker, db.PriceEOD.date.in_(look)))
    if z is not None and z >= sp["same_day_abs_z"]:
        f *= sp["factor"]
    if guidance_gap:
        f *= sp["guidance_gap_factor"]
    return f


def compute_priority(category: str, intensity: float, weight_pct: float, surprise: float = 1.0, pref: float = 1.0) -> float:
    base = cfg()["base"].get(category, 0.05)
    return round(max(0.0, min(100.0, 100 * base * intensity * pos_weight_factor(weight_pct) * surprise * pref)), 1)


MONTHS = {m.lower(): i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                                "September", "October", "November", "December"], start=1)}


def fiscal_label(d: dt.date) -> str:
    """Indian FY: Apr–Mar. 30 Sep 2026 -> 'Q2 FY27'."""
    q = (d.month - 4) // 3 + 1 if d.month >= 4 else (d.month + 8) // 3 + 1
    fy = d.year + 1 if d.month >= 4 else d.year
    return f"Q{q} FY{fy % 100:02d}"


def period_from_text(text: str) -> Optional[dt.date]:
    m = re.search(r"ended\s+(?:on\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", text or "")
    if not m:
        m2 = re.search(r"ended\s+(?:on\s+)?([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", text or "")
        if not m2:
            return None
        day, mon, yr = m2.group(2), m2.group(1), m2.group(3)
    else:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
    mi = MONTHS.get(mon.lower())
    if not mi:
        return None
    try:
        return dt.date(int(yr), mi, int(day))
    except ValueError:
        return None


def headline_for(ticker: str, subject: str, category: str, body: str = "") -> str:
    s = clean_subject(ticker, subject)
    if category == "results":
        d = period_from_text(subject) or period_from_text(body[:3000] if body else "")
        if d:
            basis = "consolidated" if re.search(r"consolidated", (subject or "") + (body or "")[:3000], re.I) else "standalone"
            kind = "half-year" if re.search(r"half", subject or "", re.I) and re.search(r"quarter", subject or "", re.I) else "quarter"
            s = f"{fiscal_label(d)} results ({basis}, {kind} ended {d:%d %b %Y})"
    if not s:
        s = category.replace("_", " ")
    h = f"{ticker}: {s}"
    return h if len(h) <= 70 else h[:67].rstrip() + "…"


def collapse_events(s, window_hours: int = 48) -> int:
    """Same ticker + category within `window_hours` = one event. Keep the highest-priority filing; demote the rest
    to buried with payload.collapsed_into so the brief shows one card ('+N related')."""
    rows = s.scalars(select(db.Filing).where(db.Filing.priority.is_not(None)).order_by(db.Filing.ticker, db.Filing.category, db.Filing.ts)).all()
    groups: dict[tuple, list[db.Filing]] = {}
    for f in rows:
        groups.setdefault((f.ticker, f.category), []).append(f)
    demoted = 0
    for (_, cat), fs in groups.items():
        if cat in ("investor_meetings", "unclassified"):
            continue  # already buried; collapsing them changes nothing
        cluster: list[db.Filing] = []
        clusters = []
        for f in fs:
            if cluster and (f.ts - cluster[-1].ts).total_seconds() > window_hours * 3600:
                clusters.append(cluster)
                cluster = []
            cluster.append(f)
        if cluster:
            clusters.append(cluster)
        for cl in clusters:
            if len(cl) < 2:
                continue
            primary = max(cl, key=lambda x: (x.priority or 0, (x.payload or {}).get("intensity", 0), x.ts))
            p = dict(primary.payload or {})
            p["related_count"] = len(cl) - 1
            p["related_ids"] = [x.id for x in cl if x.id != primary.id]
            p.pop("collapsed_into", None)
            primary.payload = p
            for x in cl:
                if x.id == primary.id:
                    continue
                xp = dict(x.payload or {})
                xp["collapsed_into"] = primary.id
                x.payload = xp
                x.tier = "buried"
                demoted += 1
    return demoted


def build_filing_payload(f: db.Filing) -> dict:
    payload = dict(f.payload or {})
    src = {"id": f"s_{f.id}", "label": "Filing (NSE)", "url": f.attachment_url or f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={f.ticker}"}
    chips = [{"label": "Open filing", "action": "open_source", "arg": src["id"]}]
    if f.category in ("results", "management_change", "ma", "capex", "fund_raise"):
        chips.append({"label": "Research", "action": "open_research", "arg": f.ticker})
    payload.setdefault("payload", {"summary": clean_subject(f.ticker, f.subject or "")})
    payload["sources"] = [src]
    payload["chips"] = chips
    return payload


def score_pending(rescore_all: bool = False) -> dict:
    n = 0
    tiers = {"lead": 0, "line": 0, "buried": 0}
    with db.session() as s:
        weights = {c.ticker: (c.weight or 0.0) for c in s.scalars(select(db.Company))}
        names = {c.ticker: c.name for c in s.scalars(select(db.Company))}
        q = select(db.Filing).where(db.Filing.category.is_not(None))
        if not rescore_all:
            q = q.where(db.Filing.priority.is_(None))
        for f in s.scalars(q).all():
            intensity = float((f.payload or {}).get("intensity", 1.0))
            pr = compute_priority(f.category, intensity, weights.get(f.ticker, 0.0),
                                  surprise_factor(s, f.ticker, f.ts), pref_factor(s, f.ticker, f.category))
            f.priority = pr
            f.tier = tier_for(pr)
            f.card_type = f.category
            f.headline = f.headline or headline_for(f.ticker, f.subject or "", f.category, f.body_text or "")
            payload = build_filing_payload(f)
            payload["company"] = names.get(f.ticker, payload.get("company") or f.ticker)
            f.payload = payload
            tiers[f.tier] += 1
            n += 1
        s.flush()
        collapsed = collapse_events(s)
    return {"scored": n, **tiers, "collapsed": collapsed}
