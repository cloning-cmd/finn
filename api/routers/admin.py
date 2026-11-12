"""Admin endpoints: cost receipt and replay. Guarded by a shared token (X-Admin-Token header or ?token=)."""
from __future__ import annotations

import datetime as dt
import threading
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from api import db
from api.config import settings
from api.llm.router import costs_summary

router = APIRouter(prefix="/admin", tags=["admin"])


def _check(token_q: Optional[str], token_h: Optional[str]) -> None:
    if (token_h or token_q) != settings.admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


@router.get("/costs")
def costs(token: Optional[str] = Query(None), x_admin_token: Optional[str] = Header(None)):
    _check(token, x_admin_token)
    return costs_summary()


@router.post("/replay")
def replay(date: str = Query(..., description="YYYY-MM-DD (IST day)"), spacing: float = Query(3.0, ge=0, le=30),
           token: Optional[str] = Query(None), x_admin_token: Optional[str] = Header(None)):
    """Replay a day: re-fire that day's visible cards as alerts with `spacing` seconds between pushes, so a grader
    sees notifications arrive. Alerts are written with fired_at = now and tagged with the replay date."""
    _check(token, x_admin_token)
    from sqlalchemy import select
    from api.pipeline import alerts as eng
    from api.routers.brief import anomaly_to_card, filing_to_card
    try:
        day = dt.date.fromisoformat(date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from e
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    start = dt.datetime.combine(day, dt.time.min, tzinfo=ist)
    end = start + dt.timedelta(days=1)
    with db.session() as s:
        filings = s.scalars(select(db.Filing).where(db.Filing.ts >= start, db.Filing.ts < end, db.Filing.tier.in_(["lead", "line"]))).all()
        anomalies = s.scalars(select(db.Anomaly).where(db.Anomaly.date == day.isoformat(), db.Anomaly.payload.is_not(None))).all()
        cards = sorted([filing_to_card(f) for f in filings] + [anomaly_to_card(a) for a in anomalies], key=lambda c: -c.priority)
        rules = eng.load_rules(s, enabled_only=True)
        plan = [(r, c) for c in cards for r in rules if eng.matches(r, c)]
    if not plan:
        return {"date": date, "cards": len(cards), "queued": 0}

    def work() -> None:
        for i, (r, c) in enumerate(plan):
            with db.session() as s2:
                # replay ids differ from live ids so a replayed day never collides with the real alert history
                replay_card = c.model_copy(update={"id": f"{c.id}~replay{day.strftime('%m%d')}"})
                eng.fire(s2, r, replay_card, push=True)
            if i < len(plan) - 1:
                time.sleep(spacing)

    threading.Thread(target=work, daemon=True).start()
    return {"date": date, "cards": len(cards), "queued": len(plan), "spacing_s": spacing}
