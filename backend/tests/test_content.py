"""Tests for content candidate generation (no real LLM)."""

from __future__ import annotations

import pytest

from app.models import Event
from app.models.enums import EventStatus
from app.pipeline.content import ANGLES, generate_candidates
from app.providers.base import LLMProvider


class _EchoLLM(LLMProvider):
    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        # distinct per angle because the prompt differs (Task: <instruction>)
        line = next((ln for ln in prompt.splitlines() if ln.startswith("Task:")), prompt[:40])
        return f"post :: {line}"


def _event() -> Event:
    return Event(
        title="OpenAI launches GPT-X",
        status=EventStatus.TRENDING,
        trend_score=80.0,
        personal_relevance=60.0,
        confidence_score=90.0,
    )


@pytest.mark.asyncio
async def test_generates_all_distinct_angles_ranked() -> None:
    drafts = await generate_candidates(_event(), ["OpenAI announced GPT-X"], _EchoLLM())
    assert len(drafts) == len(ANGLES)
    assert {d.angle for d in drafts} == set(ANGLES)
    # distinct strategic text per angle
    assert len({d.text for d in drafts}) == len(ANGLES)
    # ranked 1..N by viral_score desc
    assert [d.rank for d in drafts] == list(range(1, len(drafts) + 1))
    scores = [d.viral_score for d in drafts]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_contrarian_scores_high_novelty() -> None:
    drafts = await generate_candidates(_event(), [], _EchoLLM())
    by_angle = {d.angle: d for d in drafts}
    assert by_angle["contrarian"].novelty_score > by_angle["educational"].novelty_score
    assert by_angle["contrarian"].risk_score > by_angle["technical"].risk_score
