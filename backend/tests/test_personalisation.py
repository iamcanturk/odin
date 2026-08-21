"""Tests for the notification threshold and performance-aware ranking."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

from app.models import Event
from app.models.enums import EventStatus
from app.pipeline.notify import (
    OPPORTUNITY_FLOOR,
    OPPORTUNITY_THRESHOLD,
    opportunity_threshold,
)
from app.pipeline.opportunity import PERF_MAX, PERF_MIN, topic_performance_multipliers

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


async def _events(db_sessionmaker, scores: list[float]) -> None:
    async with db_sessionmaker() as session:
        for sc in scores:
            session.add(
                Event(
                    title=f"e{_uuid.uuid4().hex[:6]}", status=EventStatus.RISING,
                    first_seen_at=NOW - timedelta(hours=1), last_seen_at=NOW - timedelta(hours=1),
                    opportunity_score=sc,
                )
            )
        await session.commit()


async def test_threshold_tracks_the_actual_score_distribution(db_sessionmaker) -> None:
    """A fixed 80 fired once in the system's lifetime while 39 events crossed 50."""
    # Scores that top out around 60 — under the old constant, nothing would ever notify.
    await _events(db_sessionmaker, [float(i) for i in range(20, 61, 2)])
    async with db_sessionmaker() as session:
        threshold = await opportunity_threshold(session, now=NOW)

    assert OPPORTUNITY_FLOOR <= threshold <= OPPORTUNITY_THRESHOLD
    assert threshold < 80.0  # the whole point: it adapts down to reality


async def test_a_thin_sample_falls_back_to_the_floor(db_sessionmaker) -> None:
    """Percentiles of five events are meaningless."""
    await _events(db_sessionmaker, [10.0, 20.0, 30.0])
    async with db_sessionmaker() as session:
        assert await opportunity_threshold(session, now=NOW) == OPPORTUNITY_FLOOR


async def test_no_performance_data_means_no_multipliers(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        assert await topic_performance_multipliers(session) == {}


async def test_topics_you_do_well_on_rank_higher(db_sessionmaker) -> None:
    """Per-topic performance was measured but never used for ranking."""
    from app.models import Post, PostMetric, Topic

    async with db_sessionmaker() as session:
        session.add(Topic(name="Docker", keywords=["docker"], enabled=True))
        session.add(Topic(name="Crypto", keywords=["crypto"], enabled=True))
        await session.flush()
        # Docker posts land; crypto posts flop.
        for text, likes in [("docker tips", 200), ("docker build", 180), ("crypto coin", 1)]:
            post = Post(
                platform="x", text=text, status="posted", origin="imported",
                external_id=_uuid.uuid4().hex[:10],
            )
            session.add(post)
            await session.flush()
            session.add(PostMetric(post_id=post.id, likes=likes))
        await session.commit()

        mult = await topic_performance_multipliers(session)

    assert mult["docker"] > mult["crypto"]
    # Bounded on both sides: a weak topic is demoted, never silenced.
    assert all(PERF_MIN <= v <= PERF_MAX for v in mult.values())
