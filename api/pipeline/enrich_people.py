"""People enrichment: management-change filings → PeoplePayload (bio from the filing).

The cheap model only *locates* text (name, role, kind of change, verbatim profile sentences, prior roles). Code then
verifies every line against the filing (rapidfuzz partial ratio ≥ 85, numbers must match), drops what is not there,
normalises the effective date, writes the headline and one-liner, and attaches sources. An optional web search
(Tavily, when TAVILY_API_KEY is set) adds at most one line from a result snippet, labelled with its domain; LinkedIn
pages are never fetched. Every card keeps working without the model: the filing summary stays as the fallback.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from api import db
from api.config import settings
from api.ingest.documents import fetch_pdf, pdf_pages
from api.llm import router
from api.models import Incoming, Outgoing, PeoplePayload, Source
from api.pipeline.score import tier_for
from api.research.verify import quote_in_text

log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "people_extract.md"
TEXT_LIMIT = 9000
HONORIFIC = re.compile(r"^(?:mr|mrs|ms|miss|shri|smt|sri|dr|prof|ca|cs)\.?\s+", re.I)
SENIOR = re.compile(r"managing director|chief executive|\bceo\b|\bmd\b|chief financial|\bcfo\b|whole[- ]time director|executive director|chairman|chairperson|company secretary|compliance officer", re.I)
TOP = re.compile(r"managing director|chief executive|\bceo\b|\bmd\b|chief financial|\bcfo\b|chairman|chairperson", re.I)
ROLE_RANK = [("managing director|chief executive|\\bceo\\b|\\bmd\\b", 0), ("chief financial|\\bcfo\\b", 1), ("chairman|chairperson", 2),
             ("whole[- ]time|executive director", 3), ("company secretary|compliance", 4), ("independent director", 5)]
ABBREV = [(r"chief executive officer", "CEO"), (r"chief financial officer", "CFO"), (r"chief operating officer", "COO"),
          (r"chief information security officer", "CISO"), (r"chief technology officer", "CTO"), (r"managing director", "MD"),
          (r"whole[- ]time director", "WTD"), (r"independent director", "ID"), (r"non[- ]executive", "non-exec")]
VERB = {"appointment": "appointed", "resignation": "resigns as", "retirement": "retires as", "cessation": "steps down as"}
MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
DATE_DMY = re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS})[a-z]*,?\s+(\d{{4}})", re.I)
DATE_MDY = re.compile(rf"({MONTHS})[a-z]*\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", re.I)
DATE_NUM = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})")


# ----------------------------------------------------------------------------- model output


class ChangeOut(BaseModel):
    name: str
    role: str = ""
    change: str = "appointment"
    effective_date: Optional[str] = None
    profile_lines: list[str] = Field(default_factory=list)
    prior_roles: list[str] = Field(default_factory=list)
    replaces: Optional[str] = None


class PeopleOut(BaseModel):
    changes: list[ChangeOut] = Field(default_factory=list)


# ----------------------------------------------------------------------------- pure helpers (tested)


def short_name(name: str) -> str:
    n = re.sub(r"\s+", " ", name or "").strip().strip(",.")
    n = HONORIFIC.sub("", n)
    n = re.sub(r"\s*\(DIN[^)]*\)", "", n, flags=re.I)
    return n.strip()


def name_in_text(name: str, text: str) -> bool:
    parts = [p for p in re.split(r"[\s.]+", short_name(name).lower()) if len(p) > 1]
    if not parts:
        return False
    t = (text or "").lower()
    return all(p in t for p in parts[-2:])  # surname (and the token before it) must appear


def parse_date(s: Optional[str]) -> Optional[str]:
    """'7th September 2026' / 'September 7, 2026' / '07.09.2026' → '2026-09-07'. None when unparseable."""
    if not s:
        return None
    m = DATE_DMY.search(s)
    if m:
        d, mon, y = m.group(1), m.group(2), m.group(3)
    else:
        m = DATE_MDY.search(s)
        if m:
            mon, d, y = m.group(1), m.group(2), m.group(3)
        else:
            m = DATE_NUM.search(s)
            if not m:
                return None
            d, mon, y = m.group(1), m.group(2), m.group(3)
    try:
        if mon.isdigit():
            return dt.date(int(y), int(mon), int(d)).isoformat()
        mi = [k[:3] for k in MONTHS.split("|")[:12]].index(mon[:3].lower()) + 1
        return dt.date(int(y), mi, int(d)).isoformat()
    except ValueError:
        return None


def role_rank(role: str) -> int:
    if re.search(r"emeritus|honorary", role or "", re.I):
        return 8  # a courtesy title, not a job
    for pat, rank in ROLE_RANK:
        if re.search(pat, role or "", re.I):
            return rank
    return 9


def is_top(role: str) -> bool:
    return bool(TOP.search(role or "")) and not re.search(r"emeritus|honorary", role or "", re.I)


def verify_change(c: ChangeOut, text: str) -> Optional[ChangeOut]:
    """Keep only what the filing supports. Returns None when even the name is not in the text."""
    if not name_in_text(c.name, text):
        return None
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in c.profile_lines]
    lines = [ln for ln in lines if quote_in_text(ln, text)][:3]
    roles = [r.strip() for r in c.prior_roles if r and quote_in_text(r, text)][:4]
    change = c.change if c.change in VERB else "appointment"
    eff = parse_date(c.effective_date)
    if eff and eff[:4] not in (text or ""):
        eff = None
    rep = c.replaces if c.replaces and name_in_text(c.replaces, text) else None
    return ChangeOut(name=short_name(c.name), role=(c.role or "").strip(" ."), change=change, effective_date=eff,
                     profile_lines=lines, prior_roles=roles, replaces=short_name(rep) if rep else None)


def pick_primary(changes: list[ChangeOut]) -> Optional[ChangeOut]:
    """The most senior change; an appointment wins a tie (the incoming person is who the reader wants)."""
    if not changes:
        return None
    leaving = {c.name.lower() for c in changes if c.change != "appointment"}
    # the same person leaving one role and taking a courtesy title: the departure is the news
    pool = [c for c in changes if not (c.change == "appointment" and c.name.lower() in leaving)] or changes
    return sorted(pool, key=lambda c: (role_rank(c.role), 0 if c.change == "appointment" else 1))[0]


def headline_people(ticker: str, c: ChangeOut) -> str:
    role = c.role or "director"
    verb = VERB.get(c.change, "appointed")
    no_paren = re.split(r"\s*(?:\(| in the capacity of | designated)", role)[0]
    clauses = [x.strip(" -–") for x in re.split(r",| and | & ", no_paren) if x.strip(" -–")]
    senior = min(clauses, key=role_rank) if clauses else no_paren  # "…, Non-Independent Director and Vice-Chairman" → "Vice-Chairman"
    short = senior
    for long_, abbr in ABBREV:
        short = re.sub(long_, abbr, short, flags=re.I)
    for r in (role, no_paren, senior, short):
        h = f"{ticker}: {c.name} {verb} {r.strip(' -–')}"
        if len(h) <= 70 and r.strip():
            return h
    h = f"{ticker}: {c.name} {verb} {short.strip()}"
    return h[:67].rstrip() + "…"


def flags_for(c: ChangeOut, text: str, partner: Optional[ChangeOut]) -> list[str]:
    out: list[str] = []
    if is_top(c.role):
        out.append("top role")
    if re.search(r"immediate effect|with immediate", text or "", re.I):
        out.append("immediate effect")
    if c.change in ("resignation", "cessation") and not partner:
        out.append("no successor named")
    if c.change == "appointment" and not c.profile_lines:
        out.append("no profile in filing")
    if re.search(r"interim|additional charge|officiating", (c.role or "") + " " + (text or "")[:2000], re.I):
        out.append("interim")
    return out


def build_payload(primary: ChangeOut, changes: list[ChangeOut], text: str, filing_src: Source, web: list[tuple[str, Source]]) -> PeoplePayload:
    partner = next((x for x in changes if x is not primary and x.change != primary.change and x.name.lower() != primary.name.lower()
                    and (x.change == "appointment") != (primary.change == "appointment")), None)
    incoming = primary if primary.change == "appointment" else (partner if partner and partner.change == "appointment" else None)
    outgoing = primary if primary.change != "appointment" else partner
    inc = None
    if incoming:
        lines = list(incoming.profile_lines)
        srcs: list[Source] = [filing_src.model_copy(update={"quote": lines[0] if lines else None})] if lines or incoming.prior_roles else []
        for line, src in web:
            if len(lines) >= 3:
                break
            lines.append(line)
            srcs.append(src)
        inc = Incoming(name=incoming.name, bio_lines=lines[:3], prior_roles=incoming.prior_roles, bio_sources=srcs)
    out = Outgoing(name=outgoing.name) if outgoing else (Outgoing(name=primary.replaces) if primary.replaces else None)
    return PeoplePayload(role=primary.role or "Director", change=primary.change, incoming=inc, outgoing=out,
                         effective_date=primary.effective_date, flags=flags_for(primary, text, partner))


def one_liner_for(p: PeoplePayload) -> Optional[str]:
    bits: list[str] = []
    if p.effective_date:
        try:
            bits.append("from " + dt.date.fromisoformat(p.effective_date).strftime("%d %b %Y"))
        except ValueError:
            pass
    if p.incoming and p.incoming.prior_roles:
        bits.append("previously " + p.incoming.prior_roles[0])
    elif p.incoming and p.incoming.bio_lines:
        bits.append(p.incoming.bio_lines[0])
    elif p.outgoing and p.incoming is None and p.change != "appointment":
        bits.append("successor not named in the filing")
    s = " · ".join(bits)
    return (s if len(s) <= 140 else s[:137].rstrip() + "…") or None


# ----------------------------------------------------------------------------- text + web


def filing_text(f: db.Filing) -> str:
    text = (f.body_text or "").strip()
    if len(text) < 300 and f.attachment_url and f.attachment_url.lower().endswith(".pdf"):
        p = fetch_pdf(f.attachment_url)
        if p is not None:
            pages, scanned = pdf_pages(p, 4)
            if not scanned:
                text = "\n".join(pages)
    return re.sub(r"[ \t]+", " ", text)[:TEXT_LIMIT]


def web_bio(name: str, company: str) -> list[tuple[str, Source]]:
    """One snippet line from a web search result (title + first sentence), labelled by domain. Empty without a key."""
    if not settings.tavily_api_key:
        return []
    try:
        import httpx
        r = httpx.post("https://api.tavily.com/search", json={"api_key": settings.tavily_api_key, "query": f'"{name}" {company}',
                                                               "max_results": 3, "search_depth": "basic"}, timeout=8.0)
        r.raise_for_status()
        for hit in r.json().get("results", []):
            url = hit.get("url") or ""
            if not url or "linkedin.com" in url:
                continue
            snippet = re.sub(r"\s+", " ", hit.get("content") or "").strip()
            sent = re.split(r"(?<=[.!?])\s", snippet)[0] if snippet else ""
            if len(sent) < 30:
                continue
            domain = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
            return [(sent[:160], Source(id=f"w_{abs(hash(url)) % 10**8}", label=f"Web: {domain}", url=url, quote=sent[:160]))]
    except Exception as e:  # noqa: BLE001 - web is optional
        log.info("web bio skipped for %s: %s", name, str(e)[:80])
    return []


# ----------------------------------------------------------------------------- pipeline


def extract(text: str) -> tuple[list[ChangeOut], dict]:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").replace("{{text}}", text)
    out, meta = router.call("people_extract", PROMPT_VERSION, prompt, PeopleOut, max_tokens=900)
    kept = [v for v in (verify_change(c, text) for c in out.changes) if v is not None]
    return kept, meta


def enrich_filing(f: db.Filing, company: str) -> Optional[dict]:
    text = filing_text(f)
    if len(text) < 80:
        return {"skipped": "no text"}
    changes, meta = extract(text)
    primary = pick_primary(changes)
    if primary is None:
        return {"skipped": "no verified person", "cost": meta["cost_inr"]}
    filing_src = Source(id=f"s_{f.id}", label="Filing (NSE)", url=f.attachment_url or "")
    web = web_bio(primary.name, company) if primary.change == "appointment" else []
    p = build_payload(primary, changes, text, filing_src, web)
    payload = dict(f.payload or {})
    payload["payload"] = p.model_dump()
    srcs = [s for s in payload.get("sources", []) if not str(s.get("id", "")).startswith("w_")]
    payload["sources"] = srcs + [s.model_dump() for _, s in web]
    base = float((payload.get("people") or {}).get("base_priority", f.priority or 0))  # idempotent on re-runs
    payload["people"] = {"extraction": "llm", "prompt": PROMPT_VERSION, "model": meta["model"], "cost_inr": meta["cost_inr"],
                         "verified_lines": len(p.incoming.bio_lines) if p.incoming else 0, "changes": len(changes), "base_priority": base}
    f.payload = payload
    f.headline = headline_people(f.ticker, primary)
    f.one_liner = one_liner_for(p)
    if "top role" in p.flags and base < 60:
        f.priority = min(70.0, base + 15)  # a CEO/MD/CFO/chair change is never buried by the generic scorer
        f.tier = tier_for(f.priority)
    return {"name": primary.name, "role": primary.role, "change": primary.change, "lines": len(p.incoming.bio_lines) if p.incoming else 0,
            "cost": meta["cost_inr"], "cached": meta["cached"]}


def enrich_people(days: int = 45, force: bool = False, limit: int = 60) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    done = skipped = 0
    cost = 0.0
    with db.session() as s:
        names = {c.ticker: c.name for c in s.scalars(select(db.Company)).all()}
        rows = s.scalars(select(db.Filing).where(db.Filing.category == "management_change", db.Filing.ts >= since)
                         .order_by(db.Filing.ts.desc()).limit(limit)).all()
        for f in rows:
            if not force and (f.payload or {}).get("people"):
                continue
            try:
                r = enrich_filing(f, names.get(f.ticker) or f.ticker)
            except router.LLMUnavailable as e:
                log.warning("people: model unavailable: %s", e)
                return {"done": done, "skipped": skipped, "cost_inr": round(cost, 3), "gap": str(e)}
            except Exception as e:  # noqa: BLE001 - one bad filing must not stop the run
                log.warning("people: %s failed: %s", f.id, str(e)[:120])
                skipped += 1
                continue
            if r and "skipped" in r:
                skipped += 1
                cost += r.get("cost", 0) or 0
            elif r:
                done += 1
                cost += r.get("cost", 0) or 0
    return {"done": done, "skipped": skipped, "cost_inr": round(cost, 3)}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print(enrich_people(force="--force" in sys.argv))
