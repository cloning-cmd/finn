"""Explain the Move: link an EOD anomaly to filings in [date-2d, date+1d] with priority >= threshold."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from api import db
from api.pipeline.score import cfg

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def explain(s, ticker: str, date: dt.date) -> list[db.Filing]:
    a = cfg()["anomaly"]
    start = dt.datetime.combine(date - dt.timedelta(days=a["explain_window_before_days"]), dt.time.min, tzinfo=IST)
    end = dt.datetime.combine(date + dt.timedelta(days=a["explain_window_after_days"]), dt.time.max, tzinfo=IST)
    rows = s.scalars(select(db.Filing).where(db.Filing.ticker == ticker, db.Filing.ts >= start, db.Filing.ts <= end,
                                             db.Filing.priority >= a["explain_min_priority"]).order_by(db.Filing.priority.desc())).all()
    return list(rows)
