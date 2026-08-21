"""Tests for the weekly posting target and extension-free metric refresh."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app.models import Post, PostMetric
from app.pipeline.cadence import DEFAULT_WEEKLY_GOAL, cadence, set_weekly_goal, week_bounds
from app.sources.x_syndication import fetch_public_metrics

# A Thursday, so "days left" is a real number rather than the whole week.
THURSDAY = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def test_the_week_runs_monday_to_sunday():
    start, end = week_bounds(date(2026, 8, 20))  # Thursday
    assert start == date(2026, 8, 17)
    assert end == date(2026, 8, 23)


async def _post_on(db_sessionmaker, when: datetime) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Post(platform="x", text="p", status="posted", origin="imported", posted_at=when)
        )
        await session.commit()


async def test_an_empty_week_needs_the_whole_target(db_sessionmaker):
    async with db_sessionmaker() as session:
        c = await cadence(session, now=THURSDAY)
    assert c.goal == DEFAULT_WEEKLY_GOAL
    assert c.posted == 0
    assert c.remaining == DEFAULT_WEEKLY_GOAL
    assert c.days_left == 4  # Thu, Fri, Sat, Sun
    assert c.per_day_needed == round(DEFAULT_WEEKLY_GOAL / 4, 1)
    assert c.on_track is False


async def test_posts_are_counted_into_the_right_day(db_sessionmaker):
    await _post_on(db_sessionmaker, THURSDAY - timedelta(days=2))  # Tuesday
    await _post_on(db_sessionmaker, THURSDAY)
    await _post_on(db_sessionmaker, THURSDAY)
    async with db_sessionmaker() as session:
        c = await cadence(session, now=THURSDAY)
    assert c.posted == 3
    by_label = {d.label: d.posts for d in c.by_day}
    assert by_label["Sal"] == 1
    assert by_label["Per"] == 2
    assert [d.is_future for d in c.by_day] == [False] * 4 + [True] * 3


async def test_last_weeks_posts_do_not_count(db_sessionmaker):
    await _post_on(db_sessionmaker, THURSDAY - timedelta(days=8))
    async with db_sessionmaker() as session:
        c = await cadence(session, now=THURSDAY)
    assert c.posted == 0


async def test_a_lower_goal_can_put_you_on_track(db_sessionmaker):
    for _ in range(5):
        await _post_on(db_sessionmaker, THURSDAY)
    async with db_sessionmaker() as session:
        await set_weekly_goal(session, 7)
        await session.commit()
    async with db_sessionmaker() as session:
        c = await cadence(session, now=THURSDAY)
    assert c.goal == 7
    assert c.on_track is True
    assert c.remaining == 2


async def test_the_goal_is_clamped_to_something_sane(db_sessionmaker):
    async with db_sessionmaker() as session:
        assert await set_weekly_goal(session, 0) == 1
        assert await set_weekly_goal(session, 9999) == 200
        await session.commit()


async def test_quality_counts_only_posts_that_beat_the_corpus(db_sessionmaker):
    async with db_sessionmaker() as session:
        for likes in (1, 90):
            post = Post(
                platform="x", text=f"p{likes}", status="posted",
                origin="imported", posted_at=THURSDAY,
            )
            session.add(post)
            await session.flush()
            session.add(PostMetric(post_id=post.id, likes=likes, captured_at=THURSDAY))
        await session.commit()

    corpus = [float(n) for n in range(100)]
    async with db_sessionmaker() as session:
        c = await cadence(session, now=THURSDAY, corpus_likes=corpus)
    assert c.posted == 2
    assert c.quality_posts == 1


# ---- extension-free metric refresh ----


def _syndication_response(likes: int, replies: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "__typename": "Tweet",
            "favorite_count": likes,
            "conversation_count": replies,
            "text": "hello",
        },
        headers={"content-type": "application/json"},
    )


async def test_a_tombstone_is_data_not_an_error():
    """Deleted and protected tweets return HTML; that must not raise."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html>gone</html>")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_public_metrics("123", client=client)
    assert result.found is False


async def test_public_metrics_are_written_without_the_extension(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(
            Post(
                platform="x", text="p", status="posted", origin="generated",
                external_id="999", posted_at=THURSDAY,
            )
        )
        await session.commit()

    transport = httpx.MockTransport(lambda r: _syndication_response(7, 2))
    async with db_sessionmaker() as session:
        import app.pipeline.public_metrics as mod

        original = httpx.AsyncClient
        httpx.AsyncClient = lambda **kw: original(transport=transport, **kw)
        try:
            stats = await mod.refresh_public_metrics(session, now=THURSDAY)
        finally:
            httpx.AsyncClient = original
        await session.commit()

    assert stats.updated == 1
    async with db_sessionmaker() as session:
        from sqlalchemy import select

        metric = (await session.execute(select(PostMetric))).scalar_one()
    assert metric.likes == 7
    assert metric.replies == 2
    # The public endpoint doesn't expose these; a zero would poison every ratio.
    assert metric.reposts is None
    assert metric.impressions is None


@pytest.mark.parametrize("field", ["reposts", "impressions", "bookmarks"])
def test_the_honest_limits_are_documented(field):
    from app.sources import x_syndication

    assert field in x_syndication.__doc__
