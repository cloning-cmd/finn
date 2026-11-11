"""GET /brief — the Finite Brief. POST /feedback — swipe feedback."""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import db
from api.models import Brief, BuriedGroup, BuriedItem, Card, Counts, Source, Window

router = APIRouter(tags=["brief"])
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "cards.json"
WINDOWS = {"24h": dt.timedelta(hours=24), "3d": dt.timedelta(days=3), "7d": dt.timedelta(days=7), "30d": dt.timedelta(days=30)}
MINUTES_PER_BURIED = 0.5


def build_brief(cards: list[Card], frm: dt.datetime, to: dt.datetime, as_of: Optional[str] = None) -> Brief:
    """Pure function: rank cards, split into visible (lead+line) and buried groups, compute counts."""
    visible = sorted([c for c in cards if c.tier != "buried"], key=lambda c: (-c.priority, c.ts))
    buried = [c for c in cards if c.tier == "buried"]
    groups: dict[str, list[Card]] = defaultdict(list)
    for c in buried:
        groups["unclassified" if c.type in ("price_move", "volume_spike") else c.type].append(c)
    buried_groups = [
        BuriedGroup(category=cat, count=len(items),
                    items=[BuriedItem(id=i.id, headline=i.headline, ticker=i.ticker) for i in
                           sorted(items, key=lambda c: c.ts, reverse=True)])
        for cat, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    ]
    counts = Counts(lead=sum(c.tier == "lead" for c in visible), line=sum(c.tier == "line" for c in visible), buried=len(buried))
    return Brief(window=Window(**{"from": frm.isoformat(), "to": to.isoformat()}), counts=counts,
                 minutes_saved=round(len(buried) * MINUTES_PER_BURIED, 1), cards=visible, buried=buried_groups, as_of=as_of)


def load_fixture_cards() -> list[Card]:
    return [Card.model_validate(c) for c in json.loads(FIXTURES.read_text(encoding="utf-8"))]


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def filing_to_card(f: db.Filing) -> Card:
    ts = f.ts if f.ts.tzinfo else f.ts.replace(tzinfo=IST)  # SQLite drops the offset; filings are stamped in IST
    return Card(id=f.id, type=f.card_type or f.category or "unclassified", ticker=f.ticker, company=f.payload.get("company", f.ticker) if f.payload else f.ticker,
                ts=ts.isoformat(), tier=f.tier or "buried", priority=f.priority or 0, headline=f.headline or (f.subject or "")[:70],
                one_liner=f.one_liner, payload=(f.payload or {}).get("payload", {"summary": f.subject}),
                sources=(f.payload or {}).get("sources", []), chips=(f.payload or {}).get("chips", []))


def anomaly_to_card(a: db.Anomaly) -> Card:
    return Card.model_validate(a.payload)


def resolve_window(window: str, frm: Optional[str], to: Optional[str]) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(dt.timezone.utc)
    if frm and to:
        return dt.datetime.fromisoformat(frm), dt.datetime.fromisoformat(to)
    return now - WINDOWS.get(window, WINDOWS["24h"]), now


@router.get("/brief", response_model=Brief, response_model_by_alias=True)
def get_brief(window: str = Query("24h"), frm: Optional[str] = Query(None, alias="from"), to: Optional[str] = None,
              fixture: int = 0, s: Session = Depends(db.get_db)):
    start, end = resolve_window(window, frm, to)
    if fixture:
        cards = load_fixture_cards()
        return build_brief(cards, start, end, as_of="fixture")
    filings = s.scalars(select(db.Filing).where(db.Filing.ts >= start, db.Filing.ts <= end, db.Filing.tier.is_not(None))).all()
    anomalies = s.scalars(select(db.Anomaly).where(db.Anomaly.date >= start.date().isoformat(), db.Anomaly.date <= end.date().isoformat(),
                                                   db.Anomaly.payload.is_not(None))).all()
    by_id = {f.id: f for f in filings}
    cards = [with_related(filing_to_card(f), f, by_id) for f in filings] + [anomaly_to_card(a) for a in anomalies]
    return build_brief(cards, start, end)


def with_related(card: Card, f: db.Filing, by_id: dict[str, db.Filing]) -> Card:
    """Filings collapsed into this event (same ticker+category within 48h) ride along as `s_rel_` sources, so the
    UI can show "+N related" and open each one without a contract change."""
    ids = (f.payload or {}).get("related_ids") or []
    extra = []
    for rid in ids:
        r = by_id.get(rid)
        if r is None:
            continue
        extra.append(Source(id=f"s_rel_{rid[-12:]}", label=(r.headline or r.subject or rid)[:90],
                            url=r.attachment_url or f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={r.ticker}"))
    if extra:
        card.sources = list(card.sources) + extra
    return card


class FeedbackIn(BaseModel):
    card_id: str
    action: str  # noted | less
    ticker: Optional[str] = None
    category: Optional[str] = None


@router.post("/feedback")
def post_feedback(body: FeedbackIn, s: Session = Depends(db.get_db)):
    s.add(db.Feedback(card_id=body.card_id, ticker=body.ticker, category=body.category, action=body.action))
    s.commit()
    return {"ok": True}
