"""Provider abstractions and factories (embeddings + LLM)."""

from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.embedding import HashEmbeddingProvider, LocalEmbeddingProvider
from app.providers.factory import (
    build_embedding_provider,
    build_llm_provider,
    get_embedding_provider,
    get_llm_provider,
)
from app.providers.llm import MockLLMProvider, OpenAICompatibleLLMProvider

__all__ = [
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "LLMProvider",
    "LocalEmbeddingProvider",
    "MockLLMProvider",
    "OpenAICompatibleLLMProvider",
    "build_embedding_provider",
    "build_llm_provider",
    "get_embedding_provider",
    "get_llm_provider",
]
