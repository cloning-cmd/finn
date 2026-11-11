"""Grounded Q&A: top-8 chunks (ticker, optional period) + computed tables → cheap model; escalate to the strong model
when the question asks why/compare/should/risk or the cheap answer has < 2 verified claims. Same verifier."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from api.ingest import screener as sc
from api.llm import router
from api.models import Claim, Source
from api.research import docs, financials as fin
from api.research.verify import table_number_pool, verify_claims

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "qa.md"
ESCALATE = re.compile(r"\bwhy\b|\bcompare|\bshould\b|\brisk|\bversus\b|\bvs\.?\b|\bbetter\b|\bworse\b", re.I)


class ClaimOut(BaseModel):
    text: str = Field(max_length=400)
    source_ids: list[str] = Field(default_factory=list)


class QAOut(BaseModel):
    claims: list[ClaimOut] = Field(default_factory=list)


def _tables(ticker: str) -> dict:
    try:
        data = sc.load(ticker)
    except sc.ScreenerError:
        return {}
    return {"financials": fin.financials(data).model_dump(), "trajectory": fin.trajectory(data).model_dump(),
            "quarterly": {k: v for k, v in list(fin.quarterly_actuals(data).items())[-6:]}}


def answer(ticker: str, question: str, k: int = 8) -> dict:
    t = ticker.upper()
    chunks = docs.search_chunks(t, question, k=k)
    tables = _tables(t)
    tpl = PROMPT_PATH.read_text(encoding="utf-8")
    chunk_text = "\n\n".join(f"[{c['id']}] ({c['kind']} {c['period']}, p.{c['page']}, {c['speaker'] or 'report'})\n{c['text'][:1400]}" for c in chunks)
    prompt = tpl.replace("{{ticker}}", t).replace("{{question}}", question.strip()[:500]).replace("{{tables}}", json.dumps(tables, ensure_ascii=False)[:6000]).replace("{{chunks}}", chunk_text or "(no documents ingested for this ticker)")
    source_texts = {c["id"]: c["text"] for c in chunks}
    pool = table_number_pool(tables)
    task = "qa_strong" if ESCALATE.search(question) else "qa"
    try:
        out, meta = router.call(task, PROMPT_VERSION, prompt, QAOut, max_tokens=900)
    except router.LLMUnavailable as e:
        return {"claims": [], "sources": [], "model": None, "cost": 0.0, "gaps": [str(e)]}
    kept, dropped, _ = verify_claims([Claim(text=c.text, source_ids=c.source_ids) for c in out.claims], source_texts, pool)
    cost = meta["cost_inr"]
    model = meta["model"]
    if task == "qa" and len(kept) < 2 and chunks:
        try:
            out2, meta2 = router.call("qa_strong", PROMPT_VERSION, prompt, QAOut, max_tokens=900)
            kept2, dropped2, _ = verify_claims([Claim(text=c.text, source_ids=c.source_ids) for c in out2.claims], source_texts, pool)
            if len(kept2) > len(kept):
                kept, dropped, cost, model = kept2, dropped2, cost + meta2["cost_inr"], meta2["model"]
        except router.LLMUnavailable:
            pass
    used = {sid for c in kept for sid in c.source_ids}
    sources = [Source(id=c["id"], label=f"{'AR' if c['kind'] == 'ar' else 'Concall'} {c['period']} p.{c['page']}", url=c["url"], page=c["page"], quote=c["text"][:200]).model_dump()
               for c in chunks if c["id"] in used]
    if "s_screener" in used:
        sources.append(Source(id="s_screener", label="screener.in tables", url=f"https://www.screener.in/company/{t}/consolidated/").model_dump())
    gaps = [] if kept else ["no claim could be verified against the documents"]
    if dropped:
        gaps.append(f"{dropped} unverified claim(s) removed")
    return {"claims": [c.model_dump() for c in kept], "sources": sources, "model": model, "cost": round(cost, 4), "gaps": gaps}
