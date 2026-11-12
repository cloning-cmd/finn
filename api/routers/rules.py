"""Rules CRUD + natural-language rule parsing (preview only; the client saves the previewed rule)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import db
from api.llm import router as llm
from api.models import Rule
from api.pipeline import alerts as eng

router = APIRouter(tags=["rules"])
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "nl_rule.md"
CATS = ["results", "ma", "fund_raise", "management_change", "litigation", "insider_trading", "earnings_call", "investor_meetings",
        "credit_rating", "dividend", "bonus_split", "capex", "press_release", "postal_ballot", "agm_egm", "pledging"]
CAT_WORDS = {
    "results": ["result", "earnings", "quarter"], "ma": ["acqui", "merger", "m&a", "stake", "demerger"], "fund_raise": ["qip", "fund raise", "fundrais", "rights issue", "preferential", "ncd", "borrow"],
    "management_change": ["ceo", "cfo", "md ", "resign", "appoint", "director", "management change"], "litigation": ["litigation", "court", "penalty", "sebi order", "tax demand"],
    "insider_trading": ["insider", "promoter buy", "promoter sell", "sast"], "credit_rating": ["rating", "downgrade", "upgrade", "crisil", "icra"], "dividend": ["dividend"],
    "bonus_split": ["bonus", "split"], "capex": ["capex", "capacity", "plant", "expansion"], "pledging": ["pledge"], "earnings_call": ["concall", "earnings call", "transcript"],
}


class RuleDraft(BaseModel):
    name: str
    scope: dict
    condition: dict
    channels: list[str] = Field(default_factory=lambda: ["push", "inbox"])


class ParseIn(BaseModel):
    text: str


class ParseOut(BaseModel):
    rule: Rule
    method: str  # "rule" | "llm"
    cost: float = 0.0


def _resolve_ticker(s: Session, value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().upper()
    rows = s.scalars(select(db.Company)).all()
    for c in rows:
        if c.ticker.upper() == v:
            return c.ticker
    for c in rows:
        if (c.name or "").upper().startswith(v.split(" ")[0]) or v in (c.name or "").upper():
            return c.ticker
    return v  # research works for any NSE symbol; keep what the user typed


def parse_by_rules(text: str) -> Optional[dict]:
    """Cheap deterministic parse for the common shapes; None when unsure (the LLM takes over)."""
    t = text.lower()
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    sigma = re.search(r"(\d+(?:\.\d+)?)\s*(?:sigma|σ|standard deviation|std)", t)
    mult = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|times)\s*(?:the\s+)?(?:average\s+)?volume|volume\s*(?:of\s+)?(?:over|above|more than)?\s*(\d+(?:\.\d+)?)\s*(?:x|times)", t)
    direction = "down" if re.search(r"\b(fall|falls|drop|drops|down|decline|crash|plunge)", t) else "up" if re.search(r"\b(rise|rises|jump|jumps|up|gain|rally|surge)", t) else "both"
    if mult:
        m = float(mult.group(1) or mult.group(2))
        return {"kind": "volume", "multiple": m, "lookback_days": 20}
    if ("guidance" in t or "promised" in t) and re.search(r"miss|below|short", t):
        return {"kind": "guidance_gap", "min_gap_pct": float(pct.group(1)) if pct else 0.0}
    if pct and re.search(r"move|price|stock|share|fall|drop|rise|jump|gain|decline|up|down", t):
        return {"kind": "price_move", "pct": float(pct.group(1)), "z": None, "direction": direction}
    if sigma or "unusual" in t:
        return {"kind": "price_move", "pct": None, "z": float(sigma.group(1)) if sigma else 2.5, "direction": direction}
    cats = [c for c, words in CAT_WORDS.items() if any(w in t for w in words)]
    if cats:
        return {"kind": "category", "categories": cats, "min_priority": None}
    return None


def _scope_from_text(s: Session, text: str) -> dict:
    rows = s.scalars(select(db.Company)).all()
    up = text.upper()
    for c in rows:
        first = (c.name or "").upper().split(" ")[0]
        if re.search(rf"\b{re.escape(c.ticker.upper())}\b", up) or (len(first) > 3 and re.search(rf"\b{re.escape(first)}\b", up)):
            return {"type": "ticker", "value": c.ticker}
    return {"type": "portfolio"}


@router.get("/rules", response_model=list[Rule])
def get_rules(s: Session = Depends(db.get_db)):
    out = eng.load_rules(s)
    s.commit()
    return out


@router.post("/rules", response_model=Rule)
def put_rule(rule: Rule, s: Session = Depends(db.get_db)):
    if rule.scope.type == "ticker":
        rule.scope.value = _resolve_ticker(s, rule.scope.value)
    eng.save_rule(s, rule)
    s.commit()
    return rule


@router.delete("/rules/{rule_id}")
def remove_rule(rule_id: str, s: Session = Depends(db.get_db)):
    ok = eng.delete_rule(s, rule_id)
    s.commit()
    if not ok:
        raise HTTPException(404, "rule not found")
    return {"ok": True}


@router.post("/rules/parse", response_model=ParseOut)
def parse_rule(body: ParseIn, s: Session = Depends(db.get_db)):
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "empty rule text")
    cond = parse_by_rules(text)
    scope = _scope_from_text(s, text)
    method, cost = "rule", 0.0
    name = text[:40].rstrip(" .,")
    if cond is None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8").replace("{{text}}", text)
        try:
            draft, meta = llm.call("nl_rule", PROMPT_VERSION, prompt, RuleDraft, max_tokens=400)
        except llm.LLMUnavailable as e:
            raise HTTPException(503, f"could not parse the rule: {e}") from e
        cond, method, cost = draft.condition, "llm", meta["cost_inr"]
        name = draft.name[:40] or name
        if draft.scope.get("type") == "ticker":
            scope = {"type": "ticker", "value": _resolve_ticker(s, draft.scope.get("value"))}
    try:
        rule = Rule.model_validate({"id": eng.new_rule_id(text), "name": name, "enabled": True, "scope": scope,
                                    "condition": cond, "channels": ["push", "inbox"], "source_text": text})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"parsed rule is invalid: {str(e)[:200]}") from e
    return ParseOut(rule=rule, method=method, cost=round(cost, 4))
