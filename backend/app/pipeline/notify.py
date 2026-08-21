"""Emit notifications for high-value events and operational issues (PROJECT.md §32).

De-duplicated: a given event only produces one high-opportunity notification, and a
failing source only one unread failure alert at a time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Notification, Source
from app.models.enums import EventStatus

# A fixed 80 produced exactly ONE notification in the system's lifetime while 39 events
# crossed 50 — the bar sat above what the scoring actually reaches. The threshold is now
# derived from the recent score distribution, so it tracks reality instead of a guess.
OPPORTUNITY_THRESHOLD = 80.0  # absolute ceiling; the percentile usually decides
OPPORTUNITY_PERCENTILE = 0.90
OPPORTUNITY_FLOOR = 45.0  # never notify about something genuinely unremarkable
DISTRIBUTION_WINDOW = timedelta(days=7)
MIN_SAMPLE_FOR_PERCENTILE = 20
SOURCE_FAILURE_THRESHOLD = 3
TREND_SPIKE_THRESHOLD = 0.6  # acceleration component (0..1)

HIGH_OPPORTUNITY = "high_opportunity"
SOURCE_FAILURE = "source_failure"
TREND_SPIKE = "trend_spike"


async def _exists(session: AsyncSession, *, type_: str, event_id=None, title=None) -> bool:
    stmt = select(Notification.id).where(Notification.type == type_)
    if event_id is not None:
        stmt = stmt.where(Notification.event_id == event_id)
    if title is not None:
        stmt = stmt.where(Notification.title == title, Notification.read.is_(False))
    return (await session.execute(stmt.limit(1))).first() is not None


async def opportunity_threshold(session: AsyncSession, *, now: datetime | None = None) -> float:
    """What counts as "high opportunity" for THIS user's score distribution.

    Opportunity scores depend on how many sources cover a topic and how relevant it is to
    you, so the range differs per setup. Taking the 90th percentile of the last week means
    roughly the top 10% notify, whatever the absolute numbers happen to be.
    """
    now = now or datetime.now(UTC)
    rows = list(
        (
            await session.execute(
                select(Event.opportunity_score).where(
                    Event.last_seen_at >= now - DISTRIBUTION_WINDOW,
                    Event.status != EventStatus.ARCHIVED,
                )
            )
        ).scalars()
    )
    if len(rows) < MIN_SAMPLE_FOR_PERCENTILE:
        return OPPORTUNITY_FLOOR
    ordered = sorted(rows)
    cut = ordered[min(len(ordered) - 1, int(len(ordered) * OPPORTUNITY_PERCENTILE))]
    return max(OPPORTUNITY_FLOOR, min(float(cut), OPPORTUNITY_THRESHOLD))


async def emit_for_events(
    session: AsyncSession, events: list[Event], *, threshold: float | None = None
) -> int:
    if threshold is None:
        threshold = await opportunity_threshold(session)
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


async def emit_trend_spikes(
    session: AsyncSession, events: list[Event], *, threshold: float = TREND_SPIKE_THRESHOLD
) -> int:
    """One notification per event when its trend acceleration spikes (PROJECT.md §32)."""
    count = 0
    for event in events:
        accel = float((event.velocity or {}).get("acceleration", 0.0))
        if accel < threshold:
            continue
        if await _exists(session, type_=TREND_SPIKE, event_id=event.id):
            continue
        session.add(
            Notification(
                type=TREND_SPIKE,
                severity="high",
                title=f"Trend spike: {event.title[:120]}",
                body=(
                    f"Fast-rising (acceleration {accel * 100:.0f}%), "
                    f"trend {event.trend_score:.0f}."
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
