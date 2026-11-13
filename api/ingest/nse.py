"""NSE corporate announcements ingestion. One market-wide call per window, filtered to the portfolio in code.
Spike findings: docs/DECISIONS.md "Spike findings (Phase 0)"."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from sqlalchemy import select

from api import db
from api.ingest.documents import text_from_url

log = logging.getLogger(__name__)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE}/companies-listing/corporate-filings-announcements",
}


class NSEClient:
    def __init__(self, timeout: float = 30.0):
        self.c = httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True)
        self._warm = False

    def warm(self) -> None:
        if self._warm:
            return
        self.c.get(f"{BASE}/companies-listing/corporate-filings-announcements")
        self._warm = True

    def get_json(self, path: str, params: dict, tries: int = 4):
        self.warm()
        last = None
        for i in range(tries):
            try:
                r = self.c.get(f"{BASE}{path}", params=params)
                if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                    return r.json()
                last = f"{r.status_code} {r.headers.get('content-type')}"
                if r.status_code in (401, 403):
                    self._warm = False
            except httpx.HTTPError as e:
                last = repr(e)
            time.sleep(2 * (i + 1))
            self.warm()
        raise RuntimeError(f"NSE {path} failed: {last}")

    def announcements(self, frm: dt.date, to: dt.date, symbol: Optional[str] = None) -> list[dict]:
        params = {"index": "equities", "from_date": frm.strftime("%d-%m-%Y"), "to_date": to.strftime("%d-%m-%Y")}
        if symbol:
            params["symbol"] = symbol
        data = self.get_json("/api/corporate-announcements", params)
        return data if isinstance(data, list) else []

    def financial_results(self, symbol: str) -> list[dict]:
        return self.get_json("/api/corporates-financial-results", {"index": "equities", "symbol": symbol, "period": "Quarterly"})

    def annual_reports(self, symbol: str) -> list[dict]:
        d = self.get_json("/api/annual-reports", {"index": "equities", "symbol": symbol})
        return d.get("data", []) if isinstance(d, dict) else []


def parse_ts(row: dict) -> dt.datetime:
    raw = row.get("sort_date") or row.get("an_dt") or ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return dt.datetime.now(IST)


def content_hash(row: dict) -> str:
    key = "|".join(str(row.get(k) or "") for k in ("symbol", "sort_date", "attchmntText", "attchmntFile"))
    return hashlib.sha256(key.encode()).hexdigest()


def row_to_filing(row: dict) -> dict:
    h = content_hash(row)
    return {
        "id": f"f_nse_{h[:12]}", "ticker": row["symbol"], "exchange": "NSE", "ts": parse_ts(row),
        "subject": (row.get("attchmntText") or "").strip(), "raw_category": (row.get("desc") or "").strip(),
        "attachment_url": row.get("attchmntFile") or None, "content_hash": h,
        "payload": {"company": row.get("sm_name"), "industry": row.get("smIndustry"), "has_xbrl": row.get("hasXbrl"),
                    "seq_id": row.get("seq_id"), "file_size": row.get("attFileSize")},
    }


def _fetch_body(url: Optional[str]) -> str:
    if not url or not url.lower().endswith((".pdf", ".zip")):
        return ""
    text, _ = text_from_url(url, max_pages=3)
    return text[:20000]


def ingest_filings(days: int = 30, tickers: Optional[list[str]] = None, fetch_bodies: bool = True,
                   max_bodies: int = 400, client: Optional[NSEClient] = None) -> dict:
    """Pull announcements for the window, keep portfolio symbols, insert new ones (dedupe on content_hash)."""
    with db.session() as s:
        if tickers is None:
            tickers = list(s.scalars(select(db.Company.ticker).where(db.Company.in_portfolio.is_(True))))
        known = set(s.scalars(select(db.Filing.content_hash)))
    wanted = set(tickers)
    to = dt.date.today()
    frm = to - dt.timedelta(days=days)
    client = client or NSEClient()
    rows = client.announcements(frm, to)
    mine = [r for r in rows if r.get("symbol") in wanted]
    new = [row_to_filing(r) for r in mine]
    seen: set[str] = set()
    new = [f for f in new if f["content_hash"] not in known and not (f["content_hash"] in seen or seen.add(f["content_hash"]))]
    log.info("NSE window %s..%s: %d market rows, %d portfolio, %d new", frm, to, len(rows), len(mine), len(new))

    if fetch_bodies and new:
        targets = new[:max_bodies]
        with ThreadPoolExecutor(max_workers=4) as ex:
            bodies = list(ex.map(lambda f: _fetch_body(f["attachment_url"]), targets))
        for f, b in zip(targets, bodies):
            f["body_text"] = b

    with db.session() as s:
        for f in new:
            s.add(db.Filing(**f))
    return {"market_rows": len(rows), "portfolio_rows": len(mine), "inserted": len(new), "from": str(frm), "to": str(to)}
