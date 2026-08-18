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
    # 21:00 posts clearly outperform; Wednesday (2) is the best day.
    await _seed(
        db_sessionmaker,
        [
            (9, 0, 5),
            (9, 1, 7),
            (14, 3, 10),
            (21, 2, 200),
            (21, 2, 180),
            (14, 4, 12),
        ],
    )
    async with db_sessionmaker() as session:
        t = await compute_timing(session)

    assert t.enough_data is True
    assert t.best_hour == 21
    assert t.best_day == 2
    # The winning hour normalizes to 100; quieter hours score lower.
    top = next(s for s in t.by_hour if s.key == 21)
    quiet = next(s for s in t.by_hour if s.key == 9)
    assert top.score == 100.0
    assert quiet.score < top.score
    assert top.posts == 2


async def test_timing_endpoint_shape(db_sessionmaker, client: httpx.AsyncClient) -> None:
    await _seed(db_sessionmaker, [(8, 0, 5), (8, 1, 6), (20, 2, 100), (20, 3, 90), (12, 4, 30)])
    body = (await client.get("/api/v1/performance/timing")).json()
    assert body["enough_data"] is True
    assert body["best_hour"] == 20
    assert {s["key"] for s in body["by_hour"]} == {8, 12, 20}
    assert all("label" in s and "score" in s for s in body["by_day"])
