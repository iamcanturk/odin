"""Tests for LLM enrichment gating and parsing (no real LLM)."""

from __future__ import annotations

import pytest

from app.models import Event
from app.models.enums import EventStatus
from app.pipeline.enrich import (
    build_prompt,
    enrich_event,
    parse_enrichment,
    should_enrich,
)
from app.providers.base import LLMProvider


def _event(**kw) -> Event:
    base = dict(title="x", trend_score=0.0, status=EventStatus.DISCOVERED, summary=None)
    base.update(kw)
    return Event(**base)


def test_gate_high_score_enriched() -> None:
    assert should_enrich(_event(trend_score=70), threshold=50) is True


def test_gate_low_score_skipped() -> None:
    assert should_enrich(_event(trend_score=10), threshold=50) is False


def test_gate_hot_status_enriched_even_if_low_score() -> None:
    assert should_enrich(_event(trend_score=5, status=EventStatus.TRENDING), threshold=50) is True


def test_gate_already_summarized_skipped() -> None:
    assert should_enrich(_event(trend_score=90, summary="done"), threshold=50) is False


def test_gate_topic_matched_enriched_even_if_low_score() -> None:
    # Personally-relevant (topic-matched) events always get a summary.
    assert should_enrich(_event(trend_score=5), threshold=50, has_topic=True) is True
    assert should_enrich(_event(trend_score=5), threshold=50, has_topic=False) is False


def test_parse_enrichment_plain_json() -> None:
    summary, entities = parse_enrichment('{"summary": "A thing happened.", "entities": ["OpenAI"]}')
    assert summary == "A thing happened."
    assert entities == ["OpenAI"]


def test_parse_enrichment_with_code_fence() -> None:
    raw = '```json\n{"summary": "S", "entities": ["A", "B"]}\n```'
    summary, entities = parse_enrichment(raw)
    assert summary == "S"
    assert entities == ["A", "B"]


def test_parse_enrichment_garbage_is_safe() -> None:
    assert parse_enrichment("[mock] not json") == (None, [])


def test_build_prompt_caps_items() -> None:
    prompt = build_prompt("Title", [f"item {i}" for i in range(20)])
    assert prompt.count("- item") == 8


class _JSONStub(LLMProvider):
    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        return '{"summary": "Stub summary.", "entities": ["Alpha", "Beta"]}'


@pytest.mark.asyncio
async def test_enrich_event_with_stub() -> None:
    summary, entities = await enrich_event("Title", ["a", "b"], _JSONStub())
    assert summary == "Stub summary."
    assert entities == ["Alpha", "Beta"]


class _CapturingLLM(LLMProvider):
    def __init__(self) -> None:
        self.system = ""

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        self.system = system or ""
        return '{"summary": "S", "entities": []}'


@pytest.mark.asyncio
async def test_enrich_language_in_prompt() -> None:
    tr = _CapturingLLM()
    await enrich_event("Title", ["a"], tr, language="tr")
    assert "Turkish" in tr.system
    en = _CapturingLLM()
    await enrich_event("Title", ["a"], en, language="en")
    assert "English" in en.system
