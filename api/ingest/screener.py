"""screener.in tables + document links for any NSE symbol. HTML cached 24h; 1.5s between live requests.

Everything here is deterministic parsing: numbers in Rs Cr (as screener shows them), percentages as floats.
Sections: quarters (13 quarters), profit-loss (12 years + TTM), balance-sheet, cash-flow, ratios, shareholding.
Documents: annual reports [{year, url}] and concalls [{period, transcript, ppt}] (BSE/company PDFs).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx
from selectolax.lexbor import LexborHTMLParser

from api.config import settings

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
CACHE_DIR = settings.data_path / "screener"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 24 * 3600
MIN_GAP = 1.5
_last_call = 0.0
SECTIONS = ("quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios", "shareholding")


class ScreenerError(RuntimeError):
    pass


def _fetch(url: str) -> Optional[str]:
    global _last_call
    wait = MIN_GAP - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    try:
        r = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
    except httpx.HTTPError as e:
        log.info("screener fetch error %s: %s", url, e)
        return None
    if r.status_code != 200:
        log.info("screener %s -> %s", url, r.status_code)
        return None
    return r.text


def fetch_page(symbol: str, force: bool = False) -> tuple[str, str]:
    """Return (html, basis). Consolidated page first, standalone fallback. Cached 24h on disk."""
    symbol = symbol.upper()
    for basis, path in (("consolidated", f"/company/{symbol}/consolidated/"), ("standalone", f"/company/{symbol}/")):
        p = CACHE_DIR / f"{symbol}_{basis}.html"
        if not force and p.exists() and time.time() - p.stat().st_mtime < CACHE_TTL and p.stat().st_size > 1000:
            return p.read_text(encoding="utf-8"), basis
        html = _fetch(f"https://www.screener.in{path}")
        if html and "section" in html and 'id="profit-loss"' in html:
            tree = LexborHTMLParser(html)
            pl = tree.css_first("section#profit-loss table")
            if pl is not None and pl.css("tbody tr") and basis == "consolidated" and not _has_numbers(pl):
                continue  # consolidated page exists but is empty (standalone-only company)
            p.write_text(html, encoding="utf-8")
            return html, basis
    raise ScreenerError(f"screener.in has no page for {symbol}")


def _has_numbers(table) -> bool:
    return any(num(td.text(strip=True)) is not None for tr in table.css("tbody tr") for td in tr.css("td")[1:])


def num(s: str) -> Optional[float]:
    s = (s or "").strip().replace(",", "").replace("₹", "").replace("Cr.", "").replace("%", "").strip()
    if s in ("", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _label(td) -> str:
    t = td.text(deep=False, strip=True) or td.text(strip=True)
    t = re.sub(r"\s+", " ", t).strip().rstrip("+").strip()
    return t


def parse_table(table) -> dict:
    cols = [th.text(strip=True) for th in table.css("thead th")][1:]
    rows: dict[str, list[Optional[float]]] = {}
    for tr in table.css("tbody tr"):
        tds = tr.css("td")
        if not tds:
            continue
        label = _label(tds[0])
        vals = [num(td.text(strip=True)) for td in tds[1:]]
        if not label or all(v is None for v in vals):
            continue
        rows[label] = vals[: len(cols)]
    return {"cols": cols, "rows": rows}


def parse(html: str) -> dict:
    tree = LexborHTMLParser(html)
    out: dict = {"name": None, "sections": {}, "top": {}, "about": "", "annual_reports": [], "concalls": []}
    h1 = tree.css_first("h1")
    out["name"] = h1.text(strip=True) if h1 else None
    for sid in SECTIONS:
        sec = tree.css_first(f"section#{sid}")
        tb = sec.css_first("table") if sec else None
        out["sections"][sid] = parse_table(tb) if tb is not None else {"cols": [], "rows": {}}
    for li in tree.css("#top-ratios li"):
        name = li.css_first(".name")
        value = li.css_first(".value") or li.css_first(".number")
        if name is not None and value is not None:
            out["top"][re.sub(r"\s+", " ", name.text(strip=True))] = num(value.text(strip=True))
    prof = tree.css_first(".company-profile")
    if prof is not None:
        about = prof.css_first(".about") or prof
        txt = re.sub(r"\s+", " ", about.text(separator=" ", strip=True))
        txt = re.sub(r"\[\d+\]", "", txt)
        out["about"] = txt.replace("About", "", 1).strip()[:900]
    docs = tree.css_first("section#documents")
    if docs is not None:
        for a in docs.css("a"):
            txt = re.sub(r"\s+", " ", a.text(strip=True))
            href = a.attributes.get("href", "")
            m = re.match(r"Annual Report (\d{4})", txt)
            if m and href.startswith("http") and not any(r["year"] == int(m.group(1)) for r in out["annual_reports"]):
                out["annual_reports"].append({"year": int(m.group(1)), "url": href})
        for li in docs.css(".concalls li"):
            period_el = li.css_first("div")
            period = period_el.text(strip=True) if period_el else ""
            if not re.match(r"[A-Z][a-z]{2} \d{4}$", period):
                continue
            rec = {"period": period, "transcript": None, "ppt": None}
            for a in li.css("a"):
                t = a.text(strip=True).lower()
                href = a.attributes.get("href", "")
                if t == "transcript" and href.startswith("http"):
                    rec["transcript"] = href
                elif t == "ppt" and href.startswith("http"):
                    rec["ppt"] = href
            out["concalls"].append(rec)
    out["annual_reports"].sort(key=lambda r: -r["year"])
    return out


def load(symbol: str, force: bool = False) -> dict:
    html, basis = fetch_page(symbol, force=force)
    data = parse(html)
    data["symbol"] = symbol.upper()
    data["basis"] = basis
    data["source_url"] = f"https://www.screener.in/company/{symbol.upper()}/{'consolidated/' if basis == 'consolidated' else ''}"
    data["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return data


def series(data: dict, section: str, label: str) -> tuple[list[str], list[Optional[float]]]:
    """(cols, values) for a row; label matched case-insensitively on its start."""
    sec = data["sections"].get(section) or {"cols": [], "rows": {}}
    for k, v in sec["rows"].items():
        if k.lower().startswith(label.lower()):
            return sec["cols"], v
    return sec["cols"], []


def fy_cols(data: dict, section: str = "profit-loss") -> list[int]:
    """Indices of fiscal-year columns (drop TTM / stray quarter columns)."""
    cols = data["sections"].get(section, {}).get("cols", [])
    return [i for i, c in enumerate(cols) if re.match(r"Mar \d{4}$", c)]
