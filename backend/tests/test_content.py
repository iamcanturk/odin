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


class _CapturingLLM(LLMProvider):
    """Records the system prompt so we can assert the language instruction."""

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        self.systems.append(system or "")
        return "post"


@pytest.mark.asyncio
async def test_language_flows_into_prompt() -> None:
    llm = _CapturingLLM()
    await generate_candidates(_event(), [], llm, language="tr")
    assert all("Turkish" in s for s in llm.systems)

    llm_en = _CapturingLLM()
    await generate_candidates(_event(), [], llm_en, language="en")
    assert all("English" in s for s in llm_en.systems)


@pytest.mark.asyncio
async def test_kind_filters_to_single_angle() -> None:
    drafts = await generate_candidates(_event(), [], _EchoLLM(), angles=["contrarian"])
    assert len(drafts) == 1
    assert drafts[0].angle == "contrarian"


@pytest.mark.asyncio
async def test_unknown_kind_falls_back_to_all_angles() -> None:
    drafts = await generate_candidates(_event(), [], _EchoLLM(), angles=["nonsense"])
    assert {d.angle for d in drafts} == set(ANGLES)


class _DashLLM(LLMProvider):
    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        return 'Big news — the thing shipped – and it is fast.'


@pytest.mark.asyncio
async def test_sanitize_strips_em_and_en_dashes() -> None:
    drafts = await generate_candidates(_event(), [], _DashLLM(), angles=["breaking"])
    assert "—" not in drafts[0].text
    assert "–" not in drafts[0].text
    assert drafts[0].text == "Big news, the thing shipped, and it is fast."


@pytest.mark.asyncio
async def test_length_and_voice_flow_into_system_prompt() -> None:
    llm = _CapturingLLM()
    await generate_candidates(
        _event(), [], llm, angles=["breaking"], length="long", voice="Author's voice: punchy."
    )
    assert any("longer" in s for s in llm.systems)
    assert any("punchy" in s for s in llm.systems)


@pytest.mark.asyncio
async def test_contrarian_scores_high_novelty() -> None:
    drafts = await generate_candidates(_event(), [], _EchoLLM())
    by_angle = {d.angle: d for d in drafts}
    assert by_angle["contrarian"].novelty_score > by_angle["educational"].novelty_score
    assert by_angle["contrarian"].risk_score > by_angle["technical"].risk_score


@pytest.mark.asyncio
async def test_story_and_thread_formats_in_prompt() -> None:
    llm = _CapturingLLM()
    await generate_candidates(_event(), [], llm, angles=["breaking"], length="story")
    assert any("narrative" in s or "story" in s.lower() for s in llm.systems)

    llm2 = _CapturingLLM()
    await generate_candidates(_event(), [], llm2, angles=["breaking"], length="thread")
    assert any("thread" in s.lower() for s in llm2.systems)


@pytest.mark.asyncio
async def test_general_audience_asks_for_plain_words() -> None:
    llm = _CapturingLLM()
    await generate_candidates(_event(), [], llm, angles=["breaking"], audience="general")
    assert any("non-technical" in s for s in llm.systems)
