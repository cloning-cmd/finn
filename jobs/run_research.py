"""Build (or refresh) a dossier from the CLI: python -m jobs.run_research INFY [--force] [--calls 5]"""
from __future__ import annotations

import argparse
import json
import logging

from api import db
from api.research import dossier as dz

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--calls", type=int, default=5)
    a = ap.parse_args()
    db.init_db()

    def progress(step: str, status: str, detail=None) -> None:
        print(f"  [{status:5}] {step}: {detail or ''}")

    d = dz.build(a.ticker, progress=progress, force=a.force, n_calls=a.calls)
    print(json.dumps({"ticker": d.ticker, "name": d.name, "as_of": d.as_of, "basis": d.basis, "verdict": [c.text for c in d.verdict],
                      "ledger": d.ledger.summary, "promises": len(d.ledger.promises), "bull": len(d.bull), "bear": len(d.bear),
                      "gaps": d.gaps, "cost": d.cost.model_dump()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
