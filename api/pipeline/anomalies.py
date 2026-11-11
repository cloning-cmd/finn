"""EOD anomaly detection (volatility-aware). Writes one Anomaly (+ Card JSON) per ticker-day; idempotent."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select

from api import db
from api.models import Card
from api.pipeline.explain_move import explain
from api.pipeline.score import cfg, compute_priority, tier_for

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def detect(row: db.PriceEOD, z_thr: float, pct_thr: float, vol_mult: float) -> Optional[str]:
    """Return 'price_move' | 'volume_spike' | None."""
    ret = (row.ret or 0.0) * 100
    z = row.z or 0.0
    mult = (row.volume / row.vol_avg20) if row.volume and row.vol_avg20 else 0.0
    if abs(z) >= z_thr or abs(ret) >= pct_thr:
        return "price_move"
    if mult >= vol_mult:
        return "volume_spike"
    return None


def build_card(s, row: db.PriceEOD, kind: str, company: str, weight: float, sparkline: list[float]) -> tuple[Card, list[str], bool]:
    a = cfg()["anomaly"]
    ret = (row.ret or 0.0) * 100
    z = row.z or 0.0
    mult = (row.volume / row.vol_avg20) if row.volume and row.vol_avg20 else 0.0
    date = dt.date.fromisoformat(row.date)
    filings = explain(s, row.ticker, date)
    explained_by = [f.id for f in filings]
    unexplained = not explained_by
    if kind == "price_move":
        intensity = min(a["intensity_cap"], a["intensity_floor"] + a["intensity_slope"] * abs(z))
    else:
        intensity = min(a["intensity_cap"], max(0.5, mult / (a["volume_multiple"] * 1.5)))
    pr = compute_priority(kind, intensity, weight)
    if unexplained and kind == "price_move":
        pr = min(100.0, pr + a["unexplained_bonus"])
    sign = "+" if ret >= 0 else ""
    headline = f"{row.ticker} {sign}{ret:.1f}% on {mult:.1f}x volume" if mult else f"{row.ticker} {sign}{ret:.1f}%"
    if kind == "volume_spike":
        headline = f"{row.ticker}: volume {mult:.1f}x 20d avg, price {sign}{ret:.1f}%"
    mkt = f"NIFTY {(row.mkt_ret or 0) * 100:+.1f}%" if row.mkt_ret is not None else "NIFTY n/a"
    if unexplained:
        one = f"z = {z:+.1f} vs own 60-day volatility, {mkt} same day. No filing in ±48h explains it."
    else:
        one = f"Explained by: {filings[0].headline}" if filings else None
    card = Card(
        id=f"m_{row.ticker}_{row.date}", type=kind, ticker=row.ticker, company=company,
        ts=dt.datetime.combine(date, dt.time(15, 30), tzinfo=IST).isoformat(), tier=tier_for(pr), priority=pr,
        headline=headline[:70], one_liner=(one or "")[:140] or None,
        payload={"close": round(row.close or 0, 2), "change_pct": round(ret, 2), "z": round(z, 2), "volume": int(row.volume or 0),
                 "vol_multiple": round(mult, 2), "sparkline": sparkline,
                 "window_filings": [{"id": f.id, "headline": f.headline or "", "category": f.category} for f in filings[:3]]},
        sources=[{"id": f"s_m_{row.ticker}_{row.date}", "label": "NSE EOD (yfinance)", "url": f"https://www.nseindia.com/get-quotes/equity?symbol={row.ticker}"}],
        chips=([{"label": "Open filing", "action": "open_source", "arg": f"s_{filings[0].id}"}] if filings else []) +
              [{"label": "Research", "action": "open_research", "arg": row.ticker}, {"label": "Mute moves", "action": "mute", "arg": kind}],
        explained_by=explained_by, unexplained=unexplained,
    )
    return card, explained_by, unexplained


def run_anomalies(days: int = 10, z_thr: Optional[float] = None, pct_thr: Optional[float] = None, vol_mult: Optional[float] = None) -> dict:
    a = cfg()["anomaly"]
    z_thr, pct_thr, vol_mult = z_thr or a["z"], pct_thr or a["pct"], vol_mult or a["volume_multiple"]
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    out = {"checked": 0, "price_move": 0, "volume_spike": 0, "unexplained": 0}
    with db.session() as s:
        companies = {c.ticker: c for c in s.scalars(select(db.Company).where(db.Company.in_portfolio.is_(True)))}
        rows_out = []
        for ticker, c in companies.items():
            hist = s.scalars(select(db.PriceEOD).where(db.PriceEOD.ticker == ticker).order_by(db.PriceEOD.date.desc()).limit(days + 25)).all()
            hist = list(reversed(hist))
            for i, row in enumerate(hist):
                if row.date < since:
                    continue
                out["checked"] += 1
                kind = detect(row, z_thr, pct_thr, vol_mult)
                if not kind:
                    continue
                spark = [round(h.close, 2) for h in hist[max(0, i - 19):i + 1] if h.close is not None]
                card, explained_by, unexplained = build_card(s, row, kind, c.name, c.weight or 0.0, spark)
                out[kind] += 1
                out["unexplained"] += int(unexplained)
                rows_out.append({"id": card.id, "ticker": ticker, "date": row.date, "kind": kind, "value": card.payload.change_pct,
                                 "z": card.payload.z, "vol_multiple": card.payload.vol_multiple, "explained_by": explained_by,
                                 "unexplained": unexplained, "priority": card.priority, "tier": card.tier,
                                 "payload": card.model_dump(mode="json")})
        db.upsert(s, db.Anomaly, rows_out, pk=["id"])
    return out
