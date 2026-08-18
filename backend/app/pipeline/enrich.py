"""LLM event enrichment: summary + entities for high-signal events only (cost control).

Cheap/low-signal events never hit the LLM (PROJECT.md §43). Numeric scoring stays
deterministic; the LLM is only used for language understanding (PROJECT.md §42).
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ContentItem, Event
from app.models.enums import EventStatus
from app.providers.base import LLMProvider

log = get_logger("odin.enrich")

_SYSTEM = (
    "You are an analyst. Given a news event and its sources, reply with STRICT JSON: "
    '{"summary": "<2-3 sentence neutral summary>", "entities": ["<named entity>", ...]}. '
    "No markdown, no prose outside the JSON."
)

_LANG_NAME = {"en": "English", "tr": "Turkish"}

HOT_STATUSES = {EventStatus.RISING, EventStatus.TRENDING}


def _system_for(language: str) -> str:
    name = _LANG_NAME.get(language, "English")
    return f"{_SYSTEM} Write the summary in {name}. Keep entity names as-is."


def should_enrich(event: Event, threshold: float) -> bool:
    """Gate: only enrich high-signal events that aren't already summarized."""
    if event.summary:
        return False
    return event.trend_score >= threshold or EventStatus(event.status) in HOT_STATUSES


def build_prompt(title: str, item_texts: list[str]) -> str:
    joined = "\n".join(f"- {t}" for t in item_texts[:8] if t)
    return f"Event title: {title}\n\nWhat sources are saying:\n{joined}\n\nReturn the JSON."


def parse_enrichment(raw: str) -> tuple[str | None, list[str]]:
    """Extract (summary, entities) from an LLM reply; tolerate fences / junk."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None, []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, []
    summary = data.get("summary")
    entities = data.get("entities") or []
    if not isinstance(entities, list):
        entities = []
    return (summary if isinstance(summary, str) else None), [str(e) for e in entities]


async def enrich_event(
    title: str, item_texts: list[str], llm: LLMProvider, *, language: str = "en"
) -> tuple[str | None, list[str]]:
    raw = await llm.generate(
        build_prompt(title, item_texts),
        system=_system_for(language),
        temperature=0.2,
        max_tokens=400,
    )
    return parse_enrichment(raw)


async def apply_enrichment(
    session: AsyncSession,
    events: list[Event],
    llm: LLMProvider,
    *,
    threshold: float,
    language: str = "en",
) -> int:
    """Enrich the gated subset of events. Returns the number enriched."""
    enriched = 0
    for event in events:
        if not should_enrich(event, threshold):
            continue
        rows = await session.execute(
            select(ContentItem.title, ContentItem.text)
            .where(ContentItem.event_id == event.id)
            .limit(8)
        )
        texts = [" ".join(p for p in (t, x) if p) for t, x in rows]
        summary, entities = await enrich_event(event.title, texts, llm, language=language)
        if summary:
            event.summary = summary
        if entities:
            merged = sorted({*(event.entities or []), *[e.lower() for e in entities]})
            event.entities = merged
        if summary or entities:
            enriched += 1
    log.info("enrich.done", enriched=enriched, considered=len(events))
    return enriched
