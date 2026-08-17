"""Tests for provider abstractions (no torch / no network)."""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.providers import (
    HashEmbeddingProvider,
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
    build_embedding_provider,
    build_llm_provider,
)

DIM = 384


@pytest.mark.asyncio
async def test_hash_embedding_shape_and_determinism() -> None:
    provider = HashEmbeddingProvider(dim=DIM)
    v1 = await provider.embed_text("OpenAI launches new model")
    v2 = await provider.embed_text("OpenAI launches new model")
    v3 = await provider.embed_text("different text")

    assert len(v1) == DIM
    assert v1 == v2  # deterministic
    assert v1 != v3
    # unit-normalized
    assert math.isclose(math.sqrt(sum(x * x for x in v1)), 1.0, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_hash_embedding_batch() -> None:
    provider = HashEmbeddingProvider(dim=DIM)
    vectors = await provider.embed_texts(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(v) == DIM for v in vectors)


@pytest.mark.asyncio
async def test_mock_llm_generate_and_classify() -> None:
    llm = MockLLMProvider()
    out = await llm.generate("Summarize this please")
    assert out.startswith("[mock]")
    label = await llm.classify("a story about databases", ["ai", "security", "databases"])
    assert label in {"ai", "security", "databases"}


def test_factory_selects_hash_backend() -> None:
    settings = Settings(embedding_backend="hash", embedding_dim=DIM)
    provider = build_embedding_provider(settings)
    assert isinstance(provider, HashEmbeddingProvider)
    assert provider.dim == DIM


def test_factory_llm_without_key_is_mock() -> None:
    settings = Settings(llm_api_key="")
    assert isinstance(build_llm_provider(settings), MockLLMProvider)


def test_factory_llm_with_key_is_openai_compatible() -> None:
    settings = Settings(llm_api_key="sk-test", llm_base_url="https://api.deepseek.com")
    provider = build_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.base_url == "https://api.deepseek.com"
