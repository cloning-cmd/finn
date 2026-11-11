"""Load supabase/seed/portfolio.csv into companies. Run: python -m jobs.seed"""
from __future__ import annotations

import csv

from api import db
from api.config import ROOT

CSV = ROOT / "supabase" / "seed" / "portfolio.csv"


def seed() -> int:
    rows = []
    with CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "ticker": r["ticker"].strip(), "name": r["name"].strip(), "nse_symbol": r["nse_symbol"].strip() or r["ticker"].strip(),
                "bse_code": r["bse_code"].strip() or None, "sector": r["sector"].strip(), "industry": r["industry"].strip(),
                "is_lender": r["is_lender"].strip().lower() == "true", "in_portfolio": r["in_portfolio"].strip().lower() == "true",
                "weight": float(r["weight"] or 0),
            })
    db.init_db()
    with db.session() as s:
        n = db.upsert(s, db.Company, rows, pk=["ticker"])
    return n


if __name__ == "__main__":
    print(f"seeded {seed()} companies")
