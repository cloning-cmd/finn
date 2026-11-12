"""Ingest NSE filings for the portfolio (30-day backfill first run), then classify + score. Run: python -m jobs.run_filings [days]"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import func, select

from api import db
from api.ingest.nse import ingest_filings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main(days: int | None = None) -> None:
    db.init_db()
    with db.session() as s:
        if s.scalar(select(func.count()).select_from(db.Company)) == 0:
            from jobs.seed import seed
            print("seeded", seed())
        have = s.scalar(select(func.count()).select_from(db.Filing))
    if days is None:
        days = 30 if have == 0 else 3
    print("ingest:", ingest_filings(days=days))
    try:
        from api.pipeline.classify import classify_pending  # Phase 1
        from api.pipeline.score import score_pending
        print("classified:", classify_pending())
        print("scored:", score_pending())
    except ImportError:
        print("classify/score: pipeline not built yet")
    from api.pipeline.enrich_results import enrich_results
    print("results:", enrich_results())
    from api.pipeline.alerts import evaluate
    print("alerts:", evaluate())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
