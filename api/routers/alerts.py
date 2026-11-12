"""GET /alerts — chronological inbox of fired alerts. POST /alerts/evaluate — run rules now (dev/demo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api import db
from api.models import Alert
from api.pipeline import alerts as eng

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[Alert])
def get_alerts(limit: int = Query(50, ge=1, le=200), s: Session = Depends(db.get_db)):
    out = eng.list_alerts(s, limit=limit)
    s.commit()
    return out


@router.post("/alerts/evaluate")
def evaluate_now(hours: int = Query(26, ge=1, le=24 * 60)):
    import datetime as dt
    return eng.evaluate(since=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours))
