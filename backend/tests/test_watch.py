"""Tests for the metric sampling schedule (dense in the first hour)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import Post, PostMetric
from app.pipeline.watch import is_due, posts_due, sample_interval


@pytest.fixture
async def client(db_sessionmaker, monkeypatch):
    monkeypatch.setattr(get_settings(), "ingest_token", "secret", raising=False)

    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def test_first_hour_is_sampled_densely() -> None:
    assert sample_interval(timedelta(minutes=10)) == timedelta(minutes=5)
    assert sample_interval(timedelta(hours=3)) == timedelta(minutes=30)
    assert sample_interval(timedelta(hours=12)) == timedelta(hours=1)
    assert sample_interval(timedelta(days=3)) == timedelta(hours=6)
    # Past a week we stop chasing it.
    assert sample_interval(timedelta(days=30)) is None


def test_is_due_respects_the_interval() -> None:
    fresh = timedelta(minutes=10)  # in the 5-minute bucket
    assert is_due(fresh, None) is True  # never sampled
    assert is_due(fresh, timedelta(minutes=6)) is True
    assert is_due(fresh, timedelta(minutes=2)) is False
    # An old post is never due, however long since the last sample.
    assert is_due(timedelta(days=30), timedelta(days=10)) is False


async def _post(db_sessionmaker, *, minutes_old: int, sampled_minutes_ago: int | None) -> None:
    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        post = Post(
            platform="x",
            text="t",
            status="posted",
            origin="generated",
            external_id=f"id-{minutes_old}-{sampled_minutes_ago}",
            posted_at=now - timedelta(minutes=minutes_old),
        )
        session.add(post)
        await session.flush()
        if sampled_minutes_ago is not None:
            session.add(
                PostMetric(
                    post_id=post.id,
                    likes=1,
                    captured_at=now - timedelta(minutes=sampled_minutes_ago),
                )
            )
        await session.commit()


async def test_posts_due_flags_a_fresh_unsampled_post(db_sessionmaker) -> None:
    await _post(db_sessionmaker, minutes_old=10, sampled_minutes_ago=None)
    async with db_sessionmaker() as session:
        status = await posts_due(session)
    assert status.due is True
    assert status.tracking == 1
    assert status.items[0].samples == 0


async def test_posts_due_skips_a_recently_sampled_post(db_sessionmaker) -> None:
    await _post(db_sessionmaker, minutes_old=10, sampled_minutes_ago=1)
    async with db_sessionmaker() as session:
        status = await posts_due(session)
    assert status.due is False
    assert status.tracking == 1  # still tracked, just not due yet


async def test_watch_endpoint_requires_token_and_reports(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    assert (await client.get("/api/v1/ingest/x/watch")).status_code == 401

    await _post(db_sessionmaker, minutes_old=5, sampled_minutes_ago=None)
    body = (
        await client.get("/api/v1/ingest/x/watch", headers={"X-Ingest-Token": "secret"})
    ).json()
    assert body["due"] is True
    assert body["tracking"] == 1
    assert body["items"][0]["age_minutes"] == 5
