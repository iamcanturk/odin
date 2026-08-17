"""Factories selecting concrete providers from configuration."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.embedding import HashEmbeddingProvider, LocalEmbeddingProvider
from app.providers.llm import MockLLMProvider, OpenAICompatibleLLMProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_backend == "hash":
        return HashEmbeddingProvider(dim=settings.embedding_dim)
    return LocalEmbeddingProvider(settings.embedding_model, settings.embedding_dim)


def build_llm_provider(settings: Settings) -> LLMProvider:
    # Without a key we can't call DeepSeek/OpenAI — fall back to the offline mock.
    if not settings.llm_api_key:
        return MockLLMProvider()
    return OpenAICompatibleLLMProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())
