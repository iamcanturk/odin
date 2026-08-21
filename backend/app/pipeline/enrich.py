"""LLM event enrichment: summary + entities for high-signal events only (cost control).

Cheap/low-signal events never hit the LLM (PROJECT.md §43). Numeric scoring stays
deterministic; the LLM is only used for language understanding (PROJECT.md §42).
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ContentItem, Event, EventTopic
from app.models.enums import EventStatus
from app.providers.base import LLMProvider

log = get_logger("odin.enrich")

_SYSTEM = (
    "You are an analyst. Given a news event and its sources, reply with STRICT JSON: "
    '{"title": "<a short, factual headline, max 90 chars>", '
    '"summary": "<2-3 sentence neutral summary>", "entities": ["<named entity>", ...]}. '
    "No markdown, no prose outside the JSON."
)

_LANG_NAME = {"en": "English", "tr": "Turkish"}

HOT_STATUSES = {EventStatus.RISING, EventStatus.TRENDING}


def _system_for(language: str) -> str:
    name = _LANG_NAME.get(language, "English")
    return (
        f"{_SYSTEM} Write BOTH the title and the summary in {name}. "
        "Keep product, company and person names as-is — do not translate them."
    )


def should_enrich(event: Event, threshold: float, *, has_topic: bool = False) -> bool:
    """Gate: enrich share-worthy events that aren't already summarized.

    Share-worthy = matches one of the user's topics (personally relevant), OR has enough
    trend momentum, OR is in a hot lifecycle stage. Topic-matched events always get a
    summary because those are the ones the user might post about.
    """
    if event.summary:
        return False
    return (
        has_topic
        or event.trend_score >= threshold
        or EventStatus(event.status) in HOT_STATUSES
    )


def build_prompt(title: str, item_texts: list[str]) -> str:
    joined = "\n".join(f"- {t}" for t in item_texts[:8] if t)
    return f"Event title: {title}\n\nWhat sources are saying:\n{joined}\n\nReturn the JSON."


def parse_enrichment(raw: str) -> tuple[str | None, list[str], str | None]:
    """Extract (summary, entities, title) from an LLM reply; tolerate fences / junk."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None, [], None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, [], None
    summary = data.get("summary")
    entities = data.get("entities") or []
    if not isinstance(entities, list):
        entities = []
    title = data.get("title")
    return (
        summary if isinstance(summary, str) else None,
        [str(e) for e in entities],
        title.strip()[:1000] if isinstance(title, str) and title.strip() else None,
    )


async def enrich_event(
    title: str, item_texts: list[str], llm: LLMProvider, *, language: str = "en"
) -> tuple[str | None, list[str], str | None]:
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
    # Topic-matched events are always share-worthy — fetch them in one query.
    topic_ids: set = set()
    ids = [e.id for e in events if not e.summary]
    if ids:
        rows = await session.execute(
            select(EventTopic.event_id)
            .where(EventTopic.event_id.in_(ids), EventTopic.relevance > 0)
            .distinct()
        )
        topic_ids = {r[0] for r in rows}
    for event in events:
        if not should_enrich(event, threshold, has_topic=event.id in topic_ids):
            continue
        rows = await session.execute(
            select(ContentItem.title, ContentItem.text)
            .where(ContentItem.event_id == event.id)
            .limit(8)
        )
        texts = [" ".join(p for p in (t, x) if p) for t, x in rows]
        summary, entities, local_title = await enrich_event(
            event.title, texts, llm, language=language
        )
        if summary:
            event.summary = summary
        if local_title:
            event.title_local = local_title
        if entities:
            merged = sorted({*(event.entities or []), *[e.lower() for e in entities]})
            event.entities = merged
        if summary or entities or local_title:
            enriched += 1
    log.info("enrich.done", enriched=enriched, considered=len(events))
    return enriched
