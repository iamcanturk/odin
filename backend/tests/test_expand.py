"""Tests for expanding a chosen hook into the full post."""

from __future__ import annotations

import pytest

from app.pipeline.content import expand_hook
from app.providers.base import LLMProvider

HOOK = "Docker imajlarının %90'ı gereksiz yere şişkin."


class _CapturingLLM(LLMProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.systems: list[str] = []

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        self.prompts.append(prompt)
        self.systems.append(system or "")
        return f"{HOOK} Devamı burada — multi-stage build."


@pytest.mark.asyncio
async def test_hook_reaches_the_prompt_verbatim(db_sessionmaker) -> None:
    llm = _CapturingLLM()
    async with db_sessionmaker() as session:
        await expand_hook(session, HOOK, "docker", llm, n=1)
    prompt = llm.prompts[0]
    # What you scored must be what you ship, so the hook is passed through unchanged.
    assert HOOK in prompt
    assert "VERBATIM" in prompt
    assert "docker" in prompt


@pytest.mark.asyncio
async def test_expansion_is_sanitised_and_ranked(db_sessionmaker) -> None:
    llm = _CapturingLLM()
    async with db_sessionmaker() as session:
        drafts = await expand_hook(session, HOOK, "docker", llm, n=3)
    assert len(drafts) == 3
    assert [d.rank for d in drafts] == [1, 2, 3]
    scores = [d.viral_score for d in drafts]
    assert scores == sorted(scores, reverse=True)
    assert all("—" not in d.text for d in drafts)


@pytest.mark.asyncio
async def test_general_audience_changes_the_system_prompt(db_sessionmaker) -> None:
    llm = _CapturingLLM()
    async with db_sessionmaker() as session:
        await expand_hook(session, HOOK, "docker", llm, audience="general", n=1)
    assert any("general audience" in s for s in llm.systems)
