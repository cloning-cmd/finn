"""Central config. Model IDs and secrets come ONLY from env (.env at repo root)."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///data/finn.db"
    data_dir: str = "data"

    gemini_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    cheap_model: str = "gemini/gemini-3.5-flash-lite"
    cheap_model_fallback: str = "gemini/gemini-3.1-flash-lite"
    strong_model: str = "gemini/gemini-3.5-flash"
    strong_model_fallback: str = "gemini/gemini-3-flash-preview"

    tavily_api_key: str = ""

    # Chunk retrieval: "hash" (model-free hashed TF-IDF, fits a 512 MB host) or "fastembed" (bge-small ONNX, ~430 MB).
    embed_backend: str = "hash"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:finn@example.com"

    admin_token: str = "dev"
    web_origins: str = "http://localhost:3000"

    # Approx ₹ per 1M tokens (input, output). Used for the cost receipt; updated at setup from provider pages.
    usd_inr: float = 84.0

    @property
    def task_models(self) -> dict[str, list[str]]:
        cheap = [m for m in (self.cheap_model, self.cheap_model_fallback) if m]
        strong = [m for m in (self.strong_model, self.strong_model_fallback) if m]
        return {
            "classify": cheap, "one_liner": cheap, "results_map": cheap, "people_extract": cheap,
            "nl_rule": cheap, "guidance_extract": cheap, "qa": cheap,
            "synthesize": strong, "qa_strong": strong,
        }

    @property
    def data_path(self) -> Path:
        p = ROOT / self.data_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.web_origins.split(",") if o.strip()]


settings = Settings()

# Export provider keys into env for LiteLLM
for _k, _v in {
    "GEMINI_API_KEY": settings.gemini_api_key, "GROQ_API_KEY": settings.groq_api_key,
    "ANTHROPIC_API_KEY": settings.anthropic_api_key, "OPENAI_API_KEY": settings.openai_api_key,
}.items():
    if _v and not os.environ.get(_k):
        os.environ[_k] = _v
