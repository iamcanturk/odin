"""Automatic cleanup of stale ingested content (PROJECT.md §43).

Source material ages out fast: a three-day-old headline is neither an opportunity nor
useful context, and keeping everything makes the console slower and the database bigger
for no benefit. This deletes only INGESTED material — the things ODIN can re-fetch.

Never touched: your posts, their metric history and predictions, style references,
profile snapshots. Events you actually acted on are kept too, so the learning loop can
still explain where a published post came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ContentItem, Event, ObservedTweet, Post

log = get_logger("odin.retention")

# Observed tweets are a learning corpus rather than a feed, so they get a longer life.
OBSERVED_RETENTION_MULTIPLIER = 3


@dataclass
class PurgeStats:
    items: int = 0
    events: int = 0
    observed: int = 0


async def purge_old_content(
    session: AsyncSession, *, days: int, now: datetime | None = None
) -> PurgeStats:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    stats = PurgeStats()

    # Events you published from are history, not clutter — keep them and their items.
    acted_on = select(Post.event_id).where(Post.event_id.is_not(None))

    stale_items = select(ContentItem.id).where(
        or_(
            ContentItem.published_at < cutoff,
            ContentItem.published_at.is_(None) & (ContentItem.created_at < cutoff),
        ),
        or_(ContentItem.event_id.is_(None), ContentItem.event_id.not_in(acted_on)),
    )
    stats.items = (
        await session.scalar(
            select(func.count()).select_from(stale_items.subquery())
        )
    ) or 0
    if stats.items:
        await session.execute(
            delete(ContentItem).where(ContentItem.id.in_(stale_items.scalar_subquery()))
        )

    # Then drop events that are both stale and now empty. Candidates and topic/source
    # links cascade with them.
    still_referenced = select(ContentItem.event_id).where(ContentItem.event_id.is_not(None))
    stale_events = select(Event.id).where(
        Event.last_seen_at < cutoff,
        Event.id.not_in(still_referenced),
        Event.id.not_in(acted_on),
    )
    stats.events = (
        await session.scalar(select(func.count()).select_from(stale_events.subquery()))
    ) or 0
    if stats.events:
        await session.execute(delete(Event).where(Event.id.in_(stale_events.scalar_subquery())))

    observed_cutoff = now - timedelta(days=days * OBSERVED_RETENTION_MULTIPLIER)
    stats.observed = (
        await session.scalar(
            select(func.count())
            .select_from(ObservedTweet)
            .where(ObservedTweet.observed_at < observed_cutoff)
        )
    ) or 0
    if stats.observed:
        await session.execute(
            delete(ObservedTweet).where(ObservedTweet.observed_at < observed_cutoff)
        )

    await session.commit()
    log.info(
        "retention.purged",
        days=days,
        items=stats.items,
        events=stats.events,
        observed=stats.observed,
    )
    return stats
