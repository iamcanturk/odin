"""Provider abstractions so scoring/generation aren't coupled to one vendor (PROJECT.md §41)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Turns text into fixed-dimension vectors for clustering / similarity."""

    dim: int

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per input."""

    async def embed_text(self, text: str) -> list[float]:
        (vector,) = await self.embed_texts([text])
        return vector


class LLMProvider(ABC):
    """Text generation / classification. Numerical scoring must NOT depend on this."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """Generate a completion for the prompt."""

    async def classify(self, text: str, labels: list[str]) -> str:
        """Pick the single best-fitting label for text (default: prompt the LLM)."""
        joined = ", ".join(labels)
        system = (
            "You are a strict classifier. Reply with exactly one label from the allowed "
            "list and nothing else."
        )
        prompt = f"Allowed labels: {joined}\n\nText:\n{text}\n\nLabel:"
        raw = (await self.generate(prompt, system=system, temperature=0.0, max_tokens=16)).strip()
        for label in labels:
            if label.lower() in raw.lower():
                return label
        return labels[0] if labels else raw
