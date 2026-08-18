"""Tests for notification emission rules (isolated DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import Event, Notification, Source
from app.models.enums import EventStatus, SourceType
from app.pipeline.notify import emit_for_events, emit_for_sources


def _event(opp: float) -> Event:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    return Event(
        title="Big AI news",
        status=EventStatus.TRENDING,
        first_seen_at=now,
        last_seen_at=now,
        opportunity_score=opp,
        trend_score=70,
        personal_relevance=60,
    )


async def test_high_opportunity_emits_once(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        event = _event(90)
        session.add(event)
        await session.flush()

        assert await emit_for_events(session, [event]) == 1
        # De-duped: emitting again for the same event does nothing.
        assert await emit_for_events(session, [event]) == 0
        await session.commit()
        assert await session.scalar(select(func.count(Notification.id))) == 1


async def test_low_opportunity_no_notification(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        event = _event(40)
        session.add(event)
        await session.flush()
        assert await emit_for_events(session, [event]) == 0


async def test_source_failure_emits_once(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        src = Source(name="Flaky RSS", type=SourceType.RSS, url="http://x/feed", failure_count=5)
        session.add(src)
        await session.flush()

        assert await emit_for_sources(session, [src]) == 1
        assert await emit_for_sources(session, [src]) == 0  # unread alert already exists
        await session.commit()
        note = (await session.execute(select(Notification))).scalar_one()
        assert note.type == "source_failure"
        assert note.severity == "warning"
