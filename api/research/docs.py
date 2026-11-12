"""Documents for the pull engine: latest annual report + last N concall transcripts (links from screener.in).
PDF → per-page text (PyMuPDF, cached) → chunks → vectors (api.research.embed: hashed TF-IDF by default, bge-small
when EMBED_BACKEND=fastembed; stored as float32 bytes, re-embedded lazily when the backend changes).

Transcript chunking: the participant roster (page 1-3) names the speakers; each turn starts with a roster name
on its own line (or "Name:" prefix). Turns are merged up to ~800 tokens keeping speaker + page.
Annual reports: only pages under business-overview / MD&A / segment headings are chunked.
Scanned PDFs (no text layer) are skipped and recorded as a gap. No model is involved here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from sqlalchemy import func, select

from api import db
from api.config import settings
from api.ingest.documents import fetch_pdf, pdf_pages, sha256_file
from api.research import embed

log = logging.getLogger(__name__)
TEXT_DIR = settings.data_path / "doctext"
TEXT_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_PER_CHAR = 1 / 4.2
TARGET_TOKENS = 800
MGMT_ROLE = re.compile(r"chief|officer|president|managing director|chairman|chairperson|head|director|founder|ceo|cfo|coo|cto|md\b|group|executive", re.I)
MGMT_HEADERS = re.compile(r"^(CORPORATE PARTICIPANTS|MANAGEMENT|COMPANY PARTICIPANTS|PARTICIPANTS FROM .*MANAGEMENT|MANAGEMENT PARTICIPANTS)\b", re.I)
OTHER_HEADERS = re.compile(r"^(JOU?RNALISTS|ANALYSTS|CONFERENCE CALL PARTICIPANTS|PARTICIPANTS|MODERATOR|ANALYST PARTICIPANTS|INVESTORS|MEDIA)\b", re.I)
NAME_LINE = re.compile(r"^[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,4}$")
AR_HEADINGS = re.compile(r"management discussion|management's discussion|business overview|company overview|segment|our business|operating review|review of operations|business review|about the company|chairman's message|letter to shareholders", re.I)

embed_texts = embed.embed_texts
embed_query = embed.embed_query


# ----------------------------------------------------------------------------- transcripts


def roster(pages: list[str]) -> tuple[set[str], set[str]]:
    """(management names, all roster names) from the participant list on the first pages."""
    mgmt: set[str] = set()
    names: set[str] = set()
    section = None
    for text in pages[:4]:
        lines = [ln.strip() for ln in text.splitlines()]
        for i, ln in enumerate(lines):
            if not ln:
                continue
            if MGMT_HEADERS.match(ln):
                section = "mgmt"
                continue
            if OTHER_HEADERS.match(ln):
                section = "other"
                continue
            if section and NAME_LINE.match(ln) and len(ln) <= 40 and not MGMT_ROLE.search(ln):
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                names.add(ln)
                if section == "mgmt" or (MGMT_ROLE.search(nxt) and not re.search(r"analyst|research|securities|capital|asset|fund|bank\b|journal|times|tv|news", nxt, re.I)):
                    mgmt.add(ln)
    return mgmt, names


def speaker_turns(pages: list[str], names: set[str]) -> list[dict]:
    """[{speaker, page, text}] in order. A turn starts at a line equal to a roster name or 'Name:' prefix."""
    turns: list[dict] = []
    cur: Optional[dict] = None
    known = {n.lower() for n in names} | {"moderator", "operator"}
    for pno, text in enumerate(pages, start=1):
        long_lines = sum(len(l.strip()) > 70 for l in text.splitlines())
        if pno <= 4 and re.search(MGMT_HEADERS.pattern + "|" + OTHER_HEADERS.pattern, text, re.I | re.M) and long_lines < 3:
            continue  # roster page: names + roles only, no speech
        for raw in text.splitlines():
            ln = raw.strip()
            if not ln:
                continue
            m = re.match(r"^([A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,4}):\s*(.*)$", ln)
            spk = None
            rest = ""
            if ln.lower() in known or (NAME_LINE.match(ln) and ln.lower() in known):
                spk = ln
            elif m and (m.group(1).lower() in known or len(known) <= 2):
                spk, rest = m.group(1), m.group(2)
            if spk:
                if cur and cur["text"].strip():
                    turns.append(cur)
                cur = {"speaker": spk, "page": pno, "text": rest + ("\n" if rest else "")}
                continue
            if cur is None:
                continue
            if re.match(r"^(External Document|Page \d+|\d+\s*$|©)", ln):
                continue
            cur["text"] += ln + "\n"
    if cur and cur["text"].strip():
        turns.append(cur)
    return turns


def merge_turns(turns: Iterable[dict], target_tokens: int = TARGET_TOKENS) -> list[dict]:
    """Merge consecutive turns of the same speaker and split long ones so chunks stay near the target size."""
    out: list[dict] = []
    limit = int(target_tokens / TOKENS_PER_CHAR)
    for t in turns:
        txt = re.sub(r"[ \t]+", " ", t["text"]).strip()
        if len(txt) < 30:  # role line or a bare "Thank you."
            continue
        if out and out[-1]["speaker"] == t["speaker"] and len(out[-1]["text"]) + len(txt) < limit:
            out[-1]["text"] += "\n" + txt
            continue
        while len(txt) > limit * 1.3:  # split on sentence boundary
            cut = txt.rfind(". ", 0, limit)
            cut = cut + 1 if cut > limit // 2 else limit
            out.append({"speaker": t["speaker"], "page": t["page"], "text": txt[:cut].strip()})
            txt = txt[cut:].strip()
        out.append({"speaker": t["speaker"], "page": t["page"], "text": txt})
    return out


def chunk_transcript(pages: list[str]) -> tuple[list[dict], set[str]]:
    mgmt, names = roster(pages)
    turns = speaker_turns(pages, names)
    if len(turns) < 5:  # roster not detected: fall back to 'Name:' prefixes anywhere
        turns = speaker_turns(pages, set())
    chunks = merge_turns(turns)
    for c in chunks:
        c["management"] = c["speaker"] in mgmt
    return chunks, mgmt


# ----------------------------------------------------------------------------- annual reports


def chunk_annual_report(pages: list[str], max_pages: int = 60) -> list[dict]:
    """Pages under the useful headings (overview, MD&A, segments), split to ~800 tokens, page kept."""
    picked: list[tuple[int, str]] = []
    for pno, text in enumerate(pages, start=1):
        head = text[:400]
        if AR_HEADINGS.search(head) or (picked and picked[-1][0] == pno - 1 and len(picked) < max_pages and AR_HEADINGS.search(text[:1500])):
            picked.append((pno, text))
    if not picked:  # no headings found: take the first 25 pages after the cover as a generic overview
        picked = [(p, t) for p, t in enumerate(pages[2:27], start=3) if len(t.strip()) > 300]
    limit = int(TARGET_TOKENS / TOKENS_PER_CHAR)
    out: list[dict] = []
    for pno, text in picked[:max_pages]:
        txt = re.sub(r"[ \t]+", " ", text).strip()
        while txt:
            cut = len(txt) if len(txt) <= limit * 1.3 else max(txt.rfind(". ", 0, limit) + 1, limit // 2)
            out.append({"speaker": None, "page": pno, "text": txt[:cut].strip(), "management": True})
            txt = txt[cut:].strip()
    return out


# ----------------------------------------------------------------------------- persistence


def _doc_id(ticker: str, kind: str, url: str) -> str:
    return f"d_{ticker}_{kind}_{hashlib.sha256(url.encode()).hexdigest()[:10]}"


def ingest_document(ticker: str, kind: str, period: str, url: str, max_pages: Optional[int] = None) -> dict:
    """Fetch + chunk + embed one PDF unless already in `documents`. Returns {id, chunks, scanned, cached, gap}."""
    did = _doc_id(ticker, kind, url)
    with db.session() as s:
        existing = s.get(db.Document, did)
        if existing is not None:
            n = s.scalar(select(db.Chunk.id).where(db.Chunk.document_id == did).limit(1))
            if n is not None or existing.scanned:
                return {"id": did, "chunks": 0, "scanned": bool(existing.scanned), "cached": True, "gap": None}
    path = fetch_pdf(url)
    if path is None:
        return {"id": did, "chunks": 0, "scanned": False, "cached": False, "gap": f"{kind} {period}: PDF could not be downloaded"}
    pages, scanned = pdf_pages(path, max_pages)
    text_path = TEXT_DIR / f"{did}.txt"
    text_path.write_text("\f".join(pages), encoding="utf-8")
    if scanned or not pages:
        with db.session() as s:
            s.merge(db.Document(id=did, ticker=ticker, kind=kind, period=period, url=url, sha256=sha256_file(path), text_path=str(text_path), pages=len(pages), scanned=True))
        return {"id": did, "chunks": 0, "scanned": True, "cached": False, "gap": f"{kind} {period}: scanned PDF (no text layer), skipped"}
    if kind == "concall":
        chunks, mgmt = chunk_transcript(pages)
    else:
        chunks, mgmt = chunk_annual_report(pages), set()
    vecs = embed_texts([c["text"] for c in chunks])
    with db.session() as s:
        s.merge(db.Document(id=did, ticker=ticker, kind=kind, period=period, url=url, sha256=sha256_file(path), text_path=str(text_path), pages=len(pages), scanned=False))
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            spk = c["speaker"]
            if spk and c.get("management"):
                spk = f"{spk} [mgmt]"
            s.merge(db.Chunk(id=f"{did}_{i:04d}", document_id=did, ticker=ticker, period=period, speaker=spk, page=c["page"], text=c["text"], embedding=v))
    return {"id": did, "chunks": len(chunks), "scanned": False, "cached": False, "gap": None, "management": sorted(mgmt)}


def ingest_for_ticker(ticker: str, screener_data: dict, n_calls: int = 5, progress=None) -> dict:
    """Latest AR + last n concall transcripts. Returns {documents: [...], gaps: [...]}."""
    gaps: list[str] = []
    docs: list[dict] = []
    ars = screener_data.get("annual_reports") or []
    if ars:
        ar = ars[0]
        if progress:
            progress("annual_report", "start", f"AR {ar['year']}")
        r = ingest_document(ticker, "ar", f"FY{ar['year'] % 100:02d}", ar["url"], max_pages=None)
        docs.append({"kind": "ar", "period": f"FY{ar['year'] % 100:02d}", **r})
        if r["gap"]:
            gaps.append(r["gap"])
    else:
        gaps.append("no annual report link on screener.in")
    calls = [c for c in (screener_data.get("concalls") or []) if c.get("transcript")][:n_calls]
    if not calls:
        gaps.append("no concall transcripts on screener.in")
    for c in calls:
        if progress:
            progress("transcript", "start", c["period"])
        r = ingest_document(ticker, "concall", c["period"], c["transcript"])
        docs.append({"kind": "concall", "period": c["period"], **r})
        if r["gap"]:
            gaps.append(r["gap"])
    return {"documents": docs, "gaps": gaps}


# ----------------------------------------------------------------------------- retrieval

_ROWS: dict[str, tuple[int, list[tuple]]] = {}  # ticker -> (chunk count, rows); a build adds chunks, so the count is the key
_ROWS_MAX = 6


def _chunk_rows(ticker: str) -> list[tuple]:
    """(id, text, speaker, page, period, embedding, kind, url) for every chunk of the ticker, cached per process.
    Chunks whose stored vector came from the other embedding backend are re-embedded and saved first, so switching
    EMBED_BACKEND needs no migration."""
    with db.session() as s:
        n = s.scalar(select(func.count(db.Chunk.id)).where(db.Chunk.ticker == ticker)) or 0
        hit = _ROWS.get(ticker)
        if hit and hit[0] == n:
            return hit[1]
        stmt = select(db.Chunk, db.Document.kind, db.Document.url).join(db.Document, db.Chunk.document_id == db.Document.id).where(db.Chunk.ticker == ticker)
        rows = s.execute(stmt).all()
        stale = [r[0] for r in rows if not embed.is_current(r[0].embedding)]
        if stale:
            log.info("re-embedding %d %s chunks with the %s backend", len(stale), ticker, embed.backend())
            for c, v in zip(stale, embed_texts([c.text or "" for c in stale])):
                c.embedding = v
        out = [(r[0].id, r[0].text, r[0].speaker, r[0].page, r[0].period, r[0].embedding, r[1], r[2]) for r in rows]
    if len(_ROWS) >= _ROWS_MAX:
        _ROWS.pop(next(iter(_ROWS)))
    _ROWS[ticker] = (n, out)
    return out


def search_chunks(ticker: str, query: str, k: int = 8, period: Optional[str] = None, kind: Optional[str] = None,
                  management_only: bool = False) -> list[dict]:
    """Cosine search over the ticker's chunks (a few thousand at most) in numpy. Chunks whose stored vector came
    from the other embedding backend are re-embedded and saved first, so switching EMBED_BACKEND needs no migration."""
    q = embed_query(query)
    rows = _chunk_rows(ticker)
    if period:
        rows = [r for r in rows if r[4] == period]
    if kind:
        rows = [r for r in rows if r[6] == kind]
    if not rows:
        return []
    if management_only:
        rows = [r for r in rows if (r[2] or "").endswith("[mgmt]") or r[6] == "ar"] or rows
    sims = embed.similarities(embed.stack(r[5] for r in rows), q)
    # a two-line "next question is from…" chunk can match a keyword query as well as a real answer; damp it
    sims = sims * np.array([min(1.0, len(r[1] or "") / 300.0) for r in rows], dtype=np.float32)
    top = np.argsort(-sims)[:k]
    return [{"id": rows[i][0], "text": rows[i][1], "speaker": rows[i][2], "page": rows[i][3], "period": rows[i][4],
             "kind": rows[i][6], "url": rows[i][7], "score": float(sims[i])} for i in top]


def chunks_for(ticker: str, kind: Optional[str] = None, management_only: bool = False) -> list[dict]:
    with db.session() as s:
        stmt = select(db.Chunk, db.Document.kind, db.Document.url).join(db.Document, db.Chunk.document_id == db.Document.id).where(db.Chunk.ticker == ticker).order_by(db.Chunk.id)
        if kind:
            stmt = stmt.where(db.Document.kind == kind)
        rows = s.execute(stmt).all()
    out = [{"id": c.id, "text": c.text, "speaker": c.speaker, "page": c.page, "period": c.period, "kind": k, "url": u} for c, k, u in rows]
    if management_only:
        out = [c for c in out if (c["speaker"] or "").endswith("[mgmt]")]
    return out


def latest_doc_sha(ticker: str) -> str:
    with db.session() as s:
        shas = s.scalars(select(db.Document.sha256).where(db.Document.ticker == ticker).order_by(db.Document.id)).all()
    return hashlib.sha256("|".join(shas).encode()).hexdigest()[:16] if shas else "nodocs"


def as_of_now() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="minutes")
