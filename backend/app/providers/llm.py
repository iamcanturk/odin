"""LLM providers: OpenAI-compatible (DeepSeek default) and a mock for tests/dev."""

from __future__ import annotations

from app.providers.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Offline provider used when no API key is configured. Deterministic."""

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return f"[mock] {head[:200]}"


class OpenAICompatibleLLMProvider(LLMProvider):
    """Any OpenAI-compatible chat API. DeepSeek by default via base_url.

    Uses the `openai` SDK (a core dependency). The client is created lazily.
    """

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        resp = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
