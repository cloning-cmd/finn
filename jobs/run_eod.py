"""Load EOD prices for the portfolio, then detect + explain anomalies. Run: python -m jobs.run_eod"""
from __future__ import annotations

import logging
import sys

from api import db
from api.ingest.prices import load_prices

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main(period: str = "400d") -> None:
    db.init_db()
    written = load_prices(period=period)
    print("prices:", {k: v for k, v in written.items()})
    try:
        from api.pipeline.anomalies import run_anomalies  # Phase 1
        print("anomalies:", run_anomalies())
    except ImportError:
        print("anomalies: pipeline not built yet")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "400d")
