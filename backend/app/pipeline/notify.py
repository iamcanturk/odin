"""Emit notifications for high-value events and operational issues (PROJECT.md §32).

De-duplicated: a given event only produces one high-opportunity notification, and a
failing source only one unread failure alert at a time.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Notification, Source

OPPORTUNITY_THRESHOLD = 80.0
SOURCE_FAILURE_THRESHOLD = 3

HIGH_OPPORTUNITY = "high_opportunity"
SOURCE_FAILURE = "source_failure"


async def _exists(session: AsyncSession, *, type_: str, event_id=None, title=None) -> bool:
    stmt = select(Notification.id).where(Notification.type == type_)
    if event_id is not None:
        stmt = stmt.where(Notification.event_id == event_id)
    if title is not None:
        stmt = stmt.where(Notification.title == title, Notification.read.is_(False))
    return (await session.execute(stmt.limit(1))).first() is not None


async def emit_for_events(
    session: AsyncSession, events: list[Event], *, threshold: float = OPPORTUNITY_THRESHOLD
) -> int:
    count = 0
    for event in events:
        if event.opportunity_score < threshold:
            continue
        if await _exists(session, type_=HIGH_OPPORTUNITY, event_id=event.id):
            continue
        session.add(
            Notification(
                type=HIGH_OPPORTUNITY,
                severity="high",
                title=f"High opportunity: {event.title[:120]}",
                body=(
                    f"Opportunity {event.opportunity_score:.0f}, "
                    f"trend {event.trend_score:.0f}, relevance {event.personal_relevance:.0f}."
                ),
                event_id=event.id,
            )
        )
        count += 1
    return count


async def emit_for_sources(
    session: AsyncSession, sources: list[Source], *, threshold: int = SOURCE_FAILURE_THRESHOLD
) -> int:
    count = 0
    for source in sources:
        if source.failure_count < threshold:
            continue
        title = f"Source failing: {source.name}"
        if await _exists(session, type_=SOURCE_FAILURE, title=title):
            continue
        session.add(
            Notification(
                type=SOURCE_FAILURE,
                severity="warning",
                title=title,
                body=f"{source.name} has failed {source.failure_count} times.",
            )
        )
        count += 1
    return count
