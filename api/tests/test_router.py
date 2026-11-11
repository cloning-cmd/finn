"""LLM router: cache hit, JSON repair retry, provider fallback. The provider call is patched; no network."""
import pytest
from pydantic import BaseModel

from api import db
from api.llm import router


class Out(BaseModel):
    one_liner: str
    confidence: float


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(router.settings, "gemini_api_key", "test")
    monkeypatch.setattr(router.settings, "anthropic_api_key", "test")
    db.init_db()
    with db.session() as s:
        for row in s.query(db.LLMCache).filter(db.LLMCache.task.like("t_%")).all():
            s.delete(row)


def test_cache_hit_on_second_call(monkeypatch):
    calls = []

    def fake(model, messages, max_tokens, temperature):
        calls.append(model)
        return '{"one_liner": "Revenue up 10%", "confidence": 0.9}', 100, 20, 0.05

    monkeypatch.setattr(router, "_complete", fake)
    a, m1 = router.call("t_cache", "v1", "prompt A", Out, models=["gemini/x"])
    b, m2 = router.call("t_cache", "v1", "prompt A", Out, models=["gemini/x"])
    assert a == b and m1["cached"] is False and m2["cached"] is True
    assert len(calls) == 1 and m1["cost_inr"] == 0.05
    c, m3 = router.call("t_cache", "v2", "prompt A", Out, models=["gemini/x"])  # new prompt version = new key
    assert m3["cached"] is False and len(calls) == 2
    summary = router.costs_summary()
    assert summary["by_task"]["t_cache"]["calls"] == 2 and summary["by_task"]["t_cache"]["cache_hits"] == 1


def test_repair_retry_on_bad_json(monkeypatch):
    seq = iter(['```json\n{"one_liner": "x"}\n```', '{"one_liner": "x", "confidence": 0.5}'])

    def fake(model, messages, max_tokens, temperature):
        if len(messages) > 2:
            assert "failed validation" in messages[-1]["content"]
        return next(seq), 10, 5, 0.0

    monkeypatch.setattr(router, "_complete", fake)
    out, meta = router.call("t_repair", "v1", "p", Out, models=["gemini/x"])
    assert out.confidence == 0.5 and meta["tokens_in"] == 20


def test_fallback_to_next_model(monkeypatch):
    class RateLimitError(Exception):
        status_code = 429

    def fake(model, messages, max_tokens, temperature):
        if model == "gemini/x":
            raise RateLimitError("429")
        return '{"one_liner": "ok", "confidence": 1}', 1, 1, 0.0

    monkeypatch.setattr(router, "_complete", fake)
    out, meta = router.call("t_fallback", "v1", "p", Out, models=["gemini/x", "anthropic/y"])
    assert meta["model"] == "anthropic/y" and out.one_liner == "ok"


def test_unconfigured_provider_raises(monkeypatch):
    monkeypatch.setattr(router.settings, "groq_api_key", "")
    with pytest.raises(router.LLMUnavailable):
        router.call("t_none", "v1", "p", Out, models=["groq/z"])
