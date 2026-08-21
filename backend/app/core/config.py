"""Application configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Root .env (one level above backend/). extra=ignore so frontend vars don't break loading.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    # Database (async SQLAlchemy / asyncpg)
    database_url: str = "postgresql+asyncpg://odin:odin@localhost:5432/odin"

    # Redis (ARQ)
    redis_url: str = "redis://localhost:6379/0"

    # LLM provider (DeepSeek via OpenAI-compatible API)
    # OpenAI-compatible LLM (OpenRouter by default; swap base_url/model for DeepSeek/OpenAI).
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-chat"
    # Events at/above this trend score get an LLM summary (topic-matched events always do).
    enrich_trend_threshold: float = 30.0
    # Ingested source material older than this is deleted automatically. Your own posts,
    # metrics and style data are never affected.
    retention_days: int = 3
    # Default language for generated content when not specified per-request (en | tr).
    content_language: str = "en"
    # LLM pricing (USD per 1M tokens) for cost estimation. Defaults ~ deepseek-chat.
    llm_price_in_per_m: float = 0.14
    llm_price_out_per_m: float = 0.28
    # Shared token the browser extension must send to POST /api/v1/ingest/x. Empty = disabled.
    ingest_token: str = ""

    # Single-user auth. Empty auth_password = auth DISABLED (dev). Set both in prod.
    auth_username: str = "admin"
    auth_password: str = ""
    jwt_secret: str = "change-me-in-prod"
    jwt_expire_hours: int = 168  # 7 days

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_password)

    # Embeddings (local sentence-transformers)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = Field(default=384)
    # "local" = sentence-transformers (needs the `ml` extra); "hash" = deterministic fallback.
    embedding_backend: str = "local"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
