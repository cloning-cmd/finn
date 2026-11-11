"""LLM router with SQL cache. `call(task, prompt_version, prompt, schema)`:
cache key = sha256(model | prompt_version | canonical inputs); on miss → model mapped for the task (cheap/strong),
JSON-mode completion, pydantic validation with ONE repair retry, fallback model on 429/5xx/transport errors.
Tokens and Rs cost stored per call; `costs_summary()` feeds GET /admin/costs. Numbers never come from here —
callers use the router for words (classification, one-liners, extraction, synthesis) only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select

from api import db
from api.config import settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
PROVIDER_KEYS = {"gemini": "gemini_api_key", "groq": "groq_api_key", "anthropic": "anthropic_api_key", "openai": "openai_api_key"}


class LLMUnavailable(RuntimeError):
    """No configured provider could answer. Callers degrade (gaps[]) instead of inventing."""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def cache_key(model: str, prompt_version: str, inputs: Any) -> str:
    return hashlib.sha256(f"{model}|{prompt_version}|{_canonical(inputs)}".encode()).hexdigest()


def provider_configured(model: str) -> bool:
    prov = model.split("/", 1)[0]
    attr = PROVIDER_KEYS.get(prov)
    return bool(getattr(settings, attr, "")) if attr else True


def _strip_json(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    return t[i:j + 1] if i >= 0 and j > i else t


def _complete(model: str, messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, int, int, float]:
    """One provider call. Returns (text, tokens_in, tokens_out, cost_inr). Patched in tests."""
    import litellm
    litellm.drop_params = True
    kwargs: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "timeout": 90}
    if not model.startswith("anthropic/"):
        kwargs["response_format"] = {"type": "json_object"}
    r = litellm.completion(**kwargs)
    text = r.choices[0].message.content or ""
    usage = getattr(r, "usage", None)
    tin = int(getattr(usage, "prompt_tokens", 0) or 0)
    tout = int(getattr(usage, "completion_tokens", 0) or 0)
    try:
        usd = float(litellm.completion_cost(completion_response=r) or 0.0)
    except Exception:
        usd = 0.0
    return text, tin, tout, round(usd * settings.usd_inr, 4)


def _retryable(e: Exception) -> bool:
    code = getattr(e, "status_code", None)
    name = type(e).__name__
    return code in (408, 409, 425, 429, 500, 502, 503, 504) or any(k in name for k in ("RateLimit", "Timeout", "ServiceUnavailable", "APIConnection", "InternalServer"))


def call(task: str, prompt_version: str, prompt: str, schema: Type[T], system: Optional[str] = None,
         max_tokens: int = 2048, temperature: float = 0.0, extra: Optional[dict] = None, models: Optional[list[str]] = None) -> tuple[T, dict]:
    """Returns (validated object, meta{model, cached, tokens_in, tokens_out, cost_inr})."""
    candidates = [m for m in (models or settings.task_models.get(task, [])) if provider_configured(m)]
    if not candidates:
        raise LLMUnavailable(f"no provider configured for task '{task}'")
    inputs = {"prompt": prompt, "system": system or "", "schema": schema.__name__, **(extra or {})}
    with db.session() as s:
        for model in candidates:
            key = cache_key(model, prompt_version, inputs)
            row = s.get(db.LLMCache, key)
            if row is not None:
                try:
                    obj = schema.model_validate(row.output)
                except ValidationError:
                    continue
                row.hits = (row.hits or 0) + 1
                return obj, {"model": model, "cached": True, "tokens_in": 0, "tokens_out": 0, "cost_inr": 0.0}
    sys_msg = (system or "") + "\nRespond with a single JSON object only. No prose, no markdown fences."
    messages = [{"role": "system", "content": sys_msg.strip()}, {"role": "user", "content": prompt}]
    last_err: Optional[Exception] = None
    for model in candidates:
        tin = tout = 0
        cost = 0.0
        try:
            text, a, b, c = _complete(model, messages, max_tokens, temperature)
            tin, tout, cost = tin + a, tout + b, cost + c
            try:
                obj = schema.model_validate(json.loads(_strip_json(text)))
            except (ValidationError, json.JSONDecodeError) as ve:  # one repair retry with the error shown
                repair = messages + [{"role": "assistant", "content": text},
                                     {"role": "user", "content": f"That JSON failed validation: {str(ve)[:800]}. Return the corrected JSON object only."}]
                text, a, b, c = _complete(model, repair, max_tokens, temperature)
                tin, tout, cost = tin + a, tout + b, cost + c
                obj = schema.model_validate(json.loads(_strip_json(text)))
        except Exception as e:  # noqa: BLE001 - provider errors are heterogeneous
            last_err = e
            log.warning("llm %s/%s failed: %s", task, model, str(e)[:200])
            if _retryable(e) or isinstance(e, (ValidationError, json.JSONDecodeError)):
                continue
            continue
        with db.session() as s:
            key = cache_key(model, prompt_version, inputs)
            s.merge(db.LLMCache(key=key, task=task, model=model, prompt_version=prompt_version,
                                input_hash=hashlib.sha256(_canonical(inputs).encode()).hexdigest()[:16],
                                output=obj.model_dump(), tokens_in=tin, tokens_out=tout, cost_inr=cost, hits=0))
        return obj, {"model": model, "cached": False, "tokens_in": tin, "tokens_out": tout, "cost_inr": cost}
    raise LLMUnavailable(f"all models failed for task '{task}': {last_err}")


def costs_summary() -> dict:
    with db.session() as s:
        rows = s.execute(select(db.LLMCache.task, db.LLMCache.model, func.count(), func.sum(db.LLMCache.tokens_in),
                                func.sum(db.LLMCache.tokens_out), func.sum(db.LLMCache.cost_inr), func.sum(db.LLMCache.hits))
                         .group_by(db.LLMCache.task, db.LLMCache.model)).all()
    by_task: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    calls = hits = 0
    total = 0.0
    for task, model, n, tin, tout, cost, h in rows:
        for bucket, k in ((by_task, task), (by_model, model)):
            d = bucket.setdefault(k, {"calls": 0, "cache_hits": 0, "tokens_in": 0, "tokens_out": 0, "inr": 0.0})
            d["calls"] += n
            d["cache_hits"] += int(h or 0)
            d["tokens_in"] += int(tin or 0)
            d["tokens_out"] += int(tout or 0)
            d["inr"] = round(d["inr"] + float(cost or 0), 4)
        calls += n
        hits += int(h or 0)
        total += float(cost or 0)
    pct = round(100 * hits / (calls + hits), 1) if (calls + hits) else 0.0
    return {"by_task": by_task, "by_model": by_model, "cache_hit_pct": pct, "total_inr": round(total, 2), "calls": calls, "as_of": time.strftime("%Y-%m-%dT%H:%M:%S")}
