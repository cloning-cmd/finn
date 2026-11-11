"""Synthesis: ONE strong-model call per ticker per document set. Input = code-computed tables + promise ledger +
top-k chunks; output = claims with source ids. Every claim then passes verify.py; unverified ones are dropped."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from api.llm import router
from api.models import Claim, PromiseRec, PromiseStatus, Segment
from api.research import docs
from api.research.verify import table_number_pool, verify_claims

log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "synthesize.md"


class ClaimOut(BaseModel):
    text: str = Field(max_length=400)
    source_ids: list[str] = Field(default_factory=list)


class SynthOut(BaseModel):
    verdict: list[ClaimOut] = Field(default_factory=list)
    snapshot_what: list[ClaimOut] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    ledger_narrative: list[ClaimOut] = Field(default_factory=list)
    soft_statuses: dict[str, PromiseStatus] = Field(default_factory=dict)
    bull: list[ClaimOut] = Field(default_factory=list)
    bear: list[ClaimOut] = Field(default_factory=list)


def _tables_text(tables: dict) -> str:
    return json.dumps(tables, ensure_ascii=False, indent=0)[:9000]


def _ledger_text(promises: list[PromiseRec]) -> str:
    rows = []
    for p in promises:
        rows.append({"id": p.id, "metric": p.metric, "target": p.target_text, "period": p.period, "said_in": p.said_in, "hard": p.hard,
                     "status": p.status, "actual": p.actual_text, "later": [f"{m.call}:{m.stance}" for m in p.later_mentions], "quote": p.quote[:220]})
    return json.dumps(rows, ensure_ascii=False)[:9000]


def pick_chunks(ticker: str, k_each: int = 4) -> list[dict]:
    qs = ["what the company does and its main business segments", "revenue share by segment", "outlook and guidance for the coming year",
          "key risks and headwinds", "growth drivers and opportunities", "capital allocation, capex and debt"]
    seen: dict[str, dict] = {}
    for q in qs:
        for h in docs.search_chunks(ticker, q, k=k_each, management_only=True):
            seen.setdefault(h["id"], h)
    return list(seen.values())[:24]


def synthesize(ticker: str, name: str, tables: dict, promises: list[PromiseRec], chunks: list[dict]) -> tuple[dict, dict, list[str]]:
    """Returns (sections dict with verified Claims, cost meta, gaps)."""
    gaps: list[str] = []
    tpl = PROMPT_PATH.read_text(encoding="utf-8")
    chunk_text = "\n\n".join(f"[{c['id']}] ({c['kind']} {c['period']}, p.{c['page']}, {c['speaker'] or 'report'})\n{c['text'][:1500]}" for c in chunks)
    prompt = (tpl.replace("{{ticker}}", ticker).replace("{{name}}", name).replace("{{tables}}", _tables_text(tables))
              .replace("{{ledger}}", _ledger_text(promises)).replace("{{chunks}}", chunk_text))
    empty = {"verdict": [], "snapshot_what": [], "segments": [], "ledger_narrative": [], "soft_statuses": {}, "bull": [], "bear": [], "dropped": 0, "drop_reasons": []}
    try:
        out, meta = router.call("synthesize", PROMPT_VERSION, prompt, SynthOut, max_tokens=2500)
    except router.LLMUnavailable as e:
        gaps.append(f"synthesis unavailable: {e}")
        return empty, {"inr": 0.0, "tokens_in": 0, "tokens_out": 0, "cached": 0, "calls": 0, "models": []}, gaps
    source_texts = {c["id"]: c["text"] for c in chunks}
    for p in promises:
        source_texts[p.id] = f"{p.target_text} {p.quote} {p.actual_text or ''}"
    pool = table_number_pool(tables)
    pool.extend(v for p in promises for v in (p.target_low, p.target_high, p.actual_value) if v is not None)
    result = dict(empty)
    total_dropped = 0
    reasons: list[str] = []
    for key in ("verdict", "snapshot_what", "ledger_narrative", "bull", "bear"):
        claims = [Claim(text=c.text, source_ids=c.source_ids) for c in getattr(out, key)]
        kept, dropped, why = verify_claims(claims, source_texts, pool)
        result[key] = kept
        total_dropped += dropped
        reasons.extend(why)
    result["segments"] = out.segments[:5]
    result["soft_statuses"] = out.soft_statuses
    result["dropped"] = total_dropped
    result["drop_reasons"] = reasons
    if total_dropped:
        gaps.append(f"{total_dropped} unverified claim(s) removed by the citation verifier")
    cost = {"inr": meta["cost_inr"], "tokens_in": meta["tokens_in"], "tokens_out": meta["tokens_out"], "cached": int(meta["cached"]), "calls": 1, "models": [meta["model"]]}
    return result, cost, gaps
