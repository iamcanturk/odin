"""Tests for best-time-to-post (hour/day audience curve)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.models import Post, PostMetric
from app.pipeline.performance import MIN_POSTS_FOR_TIMING, compute_timing


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed(db_sessionmaker, rows: list[tuple[int, int, int]]) -> None:
    """rows = [(hour, day_of_week, likes)]"""
    async with db_sessionmaker() as session:
        for i, (hour, dow, likes) in enumerate(rows):
            post = Post(
                platform="x",
                text=f"post {i}",
                status="posted",
                origin="imported",
                hour=hour,
                day_of_week=dow,
            )
            session.add(post)
            await session.flush()
            session.add(PostMetric(post_id=post.id, likes=likes))
        await session.commit()


async def test_refuses_to_guess_from_too_few_posts(db_sessionmaker) -> None:
    await _seed(db_sessionmaker, [(9, 0, 10), (10, 1, 20)])
    async with db_sessionmaker() as session:
        t = await compute_timing(session)
    assert t.enough_data is False
    assert t.best_hour is None
    assert t.min_posts == MIN_POSTS_FOR_TIMING


async def test_finds_best_hour_and_day(db_sessionmaker) -> None:
    # 21:00 clearly outperforms, with enough posts in that bucket to be believed.
    await _seed(
        db_sessionmaker,
        [(9, 0, 5), (9, 1, 7), (9, 3, 6), (9, 4, 5)]
        + [(21, 2, 200), (21, 2, 180), (21, 2, 190), (21, 2, 210)],
    )
    async with db_sessionmaker() as session:
        t = await compute_timing(session)

    assert t.enough_data is True
    assert t.best_hour == 21
    assert t.best_day == 2
    top = next(s for s in t.by_hour if s.key == 21)
    quiet = next(s for s in t.by_hour if s.key == 9)
    assert top.score == 100.0
    assert quiet.score < top.score


async def test_a_lucky_hour_with_two_posts_is_not_advice(db_sessionmaker) -> None:
    """The real failure: 05:00 averaged 500 from 2 posts and got crowned "best hour".

    Every other hour sat between 1.5 and 5. One post taking off must not become advice.
    """
    await _seed(
        db_sessionmaker,
        [(5, 0, 1000), (5, 1, 2)]  # the outlier bucket
        + [(20, 2, 3), (20, 3, 4), (20, 4, 3), (20, 5, 2), (20, 6, 3)],
    )
    async with db_sessionmaker() as session:
        t = await compute_timing(session)

    # 20:00 has the evidence, so it wins even though 05:00 has the bigger number.
    assert t.best_hour == 20
    # The thin bucket is still charted, just not named.
    assert any(s.key == 5 for s in t.by_hour)


async def test_no_bucket_with_enough_evidence_means_no_recommendation(
    db_sessionmaker,
) -> None:
    await _seed(db_sessionmaker, [(h, h % 7, 10) for h in range(6)])
    async with db_sessionmaker() as session:
        t = await compute_timing(session)
    assert t.enough_data is True  # enough posts overall...
    assert t.best_hour is None  # ...but no single hour has enough to claim anything


async def test_timing_endpoint_shape(db_sessionmaker, client: httpx.AsyncClient) -> None:
    await _seed(
        db_sessionmaker,
        [(8, 0, 5), (8, 1, 6)] + [(20, d, 100) for d in range(2, 6)] + [(12, 6, 30)],
    )
    body = (await client.get("/api/v1/performance/timing")).json()
    assert body["enough_data"] is True
    assert body["best_hour"] == 20
    assert {s["key"] for s in body["by_hour"]} == {8, 12, 20}
    assert all("label" in s and "score" in s for s in body["by_day"])
