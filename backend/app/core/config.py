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
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

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
