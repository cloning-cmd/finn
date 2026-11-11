"""PDF fetch + text extraction (PyMuPDF). Cached on disk by sha256(url). Detects scanned PDFs (no text layer)."""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import httpx
import pymupdf

from api.config import settings

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept": "application/pdf,*/*"}
PDF_DIR = settings.data_path / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def fetch_pdf(url: str, timeout: float = 45.0, referer: Optional[str] = None) -> Optional[Path]:
    """Download (or reuse cached) PDF. Returns None on failure / non-PDF."""
    p = PDF_DIR / f"{url_key(url)}.pdf"
    if p.exists() and p.stat().st_size > 0:
        return p
    headers = dict(UA)
    headers["Referer"] = referer or ("https://www.bseindia.com/" if "bseindia" in url else "https://www.nseindia.com/")
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if r.status_code == 200 and r.content[:5] == b"%PDF-":
                p.write_bytes(r.content)
                return p
            log.info("pdf fetch %s -> %s %s", url[:80], r.status_code, r.headers.get("content-type"))
            if r.status_code in (403, 404):
                return None
        except httpx.HTTPError as e:
            log.info("pdf fetch error %s: %s", url[:80], e)
        time.sleep(1.5 * (attempt + 1))
    return None


def pdf_pages(path: Path, max_pages: Optional[int] = None) -> tuple[list[str], bool]:
    """Return (per-page text, scanned flag). scanned = text layer essentially empty."""
    try:
        doc = pymupdf.open(path)
    except Exception as e:  # corrupt
        log.info("pdf open failed %s: %s", path, e)
        return [], True
    pages = []
    n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
    for i in range(n):
        pages.append(doc[i].get_text())
    doc.close()
    chars = sum(len(t.strip()) for t in pages)
    scanned = n > 0 and chars < 40 * n
    return pages, scanned


def text_from_url(url: str, max_pages: int = 3) -> tuple[str, bool]:
    """Convenience: fetch + first N pages joined. Returns (text, scanned)."""
    p = fetch_pdf(url)
    if not p:
        return "", False
    pages, scanned = pdf_pages(p, max_pages)
    return "\n".join(pages).strip(), scanned


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
