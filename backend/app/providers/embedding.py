"""Embedding providers: local sentence-transformers (e5) and a deterministic hash fallback."""

from __future__ import annotations

import hashlib
import math

from app.providers.base import EmbeddingProvider


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free embeddings for tests/dev (no torch).

    NOT semantically meaningful — only stable and correctly shaped. Used when the
    local model is unavailable or explicitly selected via config.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        # Spread bytes of repeated SHA-256 digests across the dimensions.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        i = 0
        while i < self.dim:
            for byte in digest:
                if i >= self.dim:
                    break
                vec[i] = (byte / 255.0) * 2.0 - 1.0
                i += 1
            digest = hashlib.sha256(digest).digest()
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class LocalEmbeddingProvider(EmbeddingProvider):
    """sentence-transformers embeddings (e.g. multilingual-e5-small).

    Requires the optional `ml` extra (`uv sync --extra ml`). The model is loaded
    lazily on first use so importing this module never pulls in torch.
    """

    def __init__(self, model_name: str, dim: int, *, prefix: str = "passage: ") -> None:
        self.model_name = model_name
        self.dim = dim
        self.prefix = prefix
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        # e5 models expect a task prefix on each input.
        prefixed = [f"{self.prefix}{t}" for t in texts]
        vectors = model.encode(prefixed, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
