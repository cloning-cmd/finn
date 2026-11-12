"""Citation verifier. Quotes must fuzzy-match their source text (rapidfuzz partial_ratio >= 85); every number in a
claim must appear in the cited sources or the computed tables (±1% after unit normalisation). Unverified claims are
dropped and counted, never rewritten.
"""
from __future__ import annotations

import re
from typing import Iterable

from rapidfuzz import fuzz

from api.models import Claim

QUOTE_MIN = 85
NUM_RE = re.compile(r"(?<![\w.])[-+]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|(?<![\w.])[-+]?\d+(?:\.\d+)?")
UNIT_MULT = {"lakh": 0.01, "lakhs": 0.01, "crore": 1.0, "crores": 1.0, "cr": 1.0, "bn": 100.0, "billion": 100.0, "mn": 0.1, "million": 0.1, "k": 0.001}


def quote_in_text(quote: str, text: str) -> bool:
    q = re.sub(r"\s+", " ", quote or "").strip()
    if len(q) < 8:
        return False
    t = re.sub(r"\s+", " ", text or "")
    if fuzz.partial_ratio(q.lower(), t.lower()) < QUOTE_MIN:
        return False
    # near-identical wording with a changed number still fails: every number in the quote must be in the text
    src = set(numbers_in(t))
    return all(any(_close(v, s) for s in src) for v in numbers_in(q))


def numbers_in(text: str, facts_only: bool = False) -> list[float]:
    """Numbers in text (Indian grouping, unit words scaled to Rs Cr). facts_only skips years and small counts
    ("3 lines", "2 segments") unless they carry %/x/bps."""
    out = []
    # "Rs.2635" / "INR.500" / "₹.12": the currency period would otherwise hide the number from NUM_RE
    text = re.sub(r"(?i)\b(rs|inr)\.(?=\d)|₹\.?(?=\d)", lambda m: m.group(0).rstrip(".") + " ", text or "")
    for m in NUM_RE.finditer(text):
        raw = m.group(0).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        if facts_only:
            after = text[m.end(): m.end() + 4].lstrip()
            measured = after.startswith(("%", "x", "×", "bps", "pp", "crore", "cr", "lakh", "bn", "mn"))
            if (1990 <= v <= 2040 and float(v).is_integer() and not measured) or (abs(v) < 10 and float(v).is_integer() and not measured):
                continue
        # unit words right after the number scale it to Rs Cr where relevant
        tail = text[m.end(): m.end() + 12].strip().lower()
        for unit, mult in UNIT_MULT.items():
            if tail.startswith(unit):
                v *= mult
                break
        out.append(v)
    return out


def _close(a: float, b: float, tol: float = 0.01) -> bool:
    if a == b:
        return True
    if abs(a) < 1e-9 or abs(b) < 1e-9:
        return abs(a - b) < 0.05
    return abs(a - b) / abs(b) <= tol


def number_supported(v: float, pool: Iterable[float]) -> bool:
    return any(_close(v, p) for p in pool)


def verify_claims(claims: list[Claim], source_texts: dict[str, str], table_numbers: Iterable[float]) -> tuple[list[Claim], int, list[str]]:
    """Keep claims whose every number appears in the cited sources (text numbers) or the table pool.
    Returns (kept, dropped_count, reasons)."""
    kept: list[Claim] = []
    dropped = 0
    reasons: list[str] = []
    table_pool = list(table_numbers)
    for c in claims:
        if not c.source_ids:
            dropped += 1
            reasons.append(f"no source: {c.text[:60]}")
            continue
        cited = [source_texts.get(sid, "") for sid in c.source_ids]
        if not any(cited) and not any(sid.startswith("s_screener") for sid in c.source_ids):
            dropped += 1
            reasons.append(f"unknown source {c.source_ids}: {c.text[:60]}")
            continue
        pool = list(table_pool)
        for t in cited:
            pool.extend(numbers_in(t))
        bad = [v for v in numbers_in(c.text, facts_only=True) if not number_supported(v, pool)]
        if bad:
            dropped += 1
            reasons.append(f"number(s) {bad[:3]} not in sources: {c.text[:60]}")
            continue
        kept.append(Claim(text=c.text, source_ids=c.source_ids, verified=True))
    return kept, dropped, reasons


def table_number_pool(*objs) -> list[float]:
    """Every number inside pydantic models / dicts / lists (recursively) → verification pool."""
    pool: list[float] = []

    def walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            pool.append(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif hasattr(o, "model_dump"):
            walk(o.model_dump())
    for o in objs:
        walk(o)
    # margins/ratios appear as both 24.0 and "24%" — add percent-point variants of fractions
    pool.extend(round(v * 100, 1) for v in list(pool) if 0 < abs(v) < 1)
    return pool
