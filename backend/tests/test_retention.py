"""Tests for automatic cleanup of stale ingested content."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import ContentItem, Event, ObservedTweet, Post, PostMetric, Source
from app.models.enums import EventStatus, Priority, SourceType
from app.pipeline.retention import purge_old_content

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


async def _source(session) -> Source:
    src = Source(
        name=f"S-{_uuid.uuid4().hex[:6]}", type=SourceType.RSS, url="https://e/f",
        category="technology", priority=Priority.MEDIUM, confidence=0.7,
    )
    session.add(src)
    await session.flush()
    return src


async def _event_with_item(session, src, *, age_days: float) -> Event:
    ts = NOW - timedelta(days=age_days)
    event = Event(title="E", status=EventStatus.RISING, first_seen_at=ts, last_seen_at=ts)
    session.add(event)
    await session.flush()
    session.add(
        ContentItem(
            source_id=src.id, event_id=event.id, content_hash=_uuid.uuid4().hex,
            title="t", published_at=ts,
        )
    )
    return event


async def test_stale_content_is_removed_but_fresh_is_kept(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        src = await _source(session)
        await _event_with_item(session, src, age_days=10)
        await _event_with_item(session, src, age_days=0.5)
        await session.commit()

        stats = await purge_old_content(session, days=3, now=NOW)

        assert stats.items == 1
        assert stats.events == 1
        assert await session.scalar(select(func.count()).select_from(ContentItem)) == 1
        assert await session.scalar(select(func.count()).select_from(Event)) == 1


async def test_events_you_published_from_are_never_purged(db_sessionmaker) -> None:
    """Those are history that explains a real post, not clutter."""
    async with db_sessionmaker() as session:
        src = await _source(session)
        event = await _event_with_item(session, src, age_days=30)
        await session.flush()
        session.add(
            Post(
                platform="x", text="the post that came from it", status="posted",
                origin="generated", external_id="1", event_id=event.id,
            )
        )
        await session.commit()

        stats = await purge_old_content(session, days=3, now=NOW)

        assert stats.events == 0
        assert stats.items == 0
        assert await session.get(Event, event.id) is not None


async def test_your_own_posts_and_metrics_survive(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        post = Post(
            platform="x", text="mine", status="posted", origin="imported",
            external_id="9", posted_at=NOW - timedelta(days=90),
        )
        session.add(post)
        await session.flush()
        session.add(PostMetric(post_id=post.id, likes=5, captured_at=NOW - timedelta(days=90)))
        await session.commit()

        await purge_old_content(session, days=3, now=NOW)

        assert await session.scalar(select(func.count()).select_from(Post)) == 1
        assert await session.scalar(select(func.count()).select_from(PostMetric)) == 1


async def test_observed_tweets_get_a_longer_window(db_sessionmaker) -> None:
    """They're a learning corpus, so they outlive the feed."""
    async with db_sessionmaker() as session:
        for age in (5, 30):  # days: inside 3*3=9d window, and outside it
            session.add(
                ObservedTweet(
                    external_id=f"o{age}", text="t", observed_at=NOW - timedelta(days=age),
                    posted_at=NOW - timedelta(days=age),
                )
            )
        await session.commit()

        stats = await purge_old_content(session, days=3, now=NOW)

        assert stats.observed == 1
        assert await session.scalar(select(func.count()).select_from(ObservedTweet)) == 1
