"""Tests for the inbound X ingestion endpoint — output-only (own posts only)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import ContentItem, Post, PostMetric


@pytest.fixture
async def client(db_sessionmaker, monkeypatch):
    monkeypatch.setattr(get_settings(), "ingest_token", "secret", raising=False)

    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _payload():
    return {
        "items": [
            {
                "id": "1001",
                "text": "My own take on GPT-X",
                "author_handle": "@me",
                "created_at": "2026-08-18T10:00:00Z",
                "metrics": {"likes": 120, "reposts": 30, "impressions": 9000},
                "is_self": True,
            },
            {"id": "1002", "text": "Someone else's tweet", "author_handle": "@other"},
        ]
    }


async def test_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/ingest/x", json=_payload())
    assert resp.status_code == 401


async def test_imports_only_own_posts_no_events(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    headers = {"X-Ingest-Token": "secret"}
    resp = await client.post("/api/v1/ingest/x", json=_payload(), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["received"] == 2
    assert body["created"] == 1  # only the is_self post
    assert body["events_created"] == 0

    async with db_sessionmaker() as session:
        # X is not an event source: no ContentItems are created.
        assert await session.scalar(select(func.count(ContentItem.id))) == 0
        # The user's own post is imported with its engagement snapshot (incl. impressions).
        assert await session.scalar(select(func.count(Post.id))) == 1
        metric = (await session.execute(select(PostMetric))).scalar_one()
        assert metric.likes == 120
        assert metric.reposts == 30
        assert metric.impressions == 9000


async def test_own_post_metrics_update_is_appended(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    headers = {"X-Ingest-Token": "secret"}
    await client.post("/api/v1/ingest/x", json=_payload(), headers=headers)

    # Re-post the same tweet with grown metrics -> a new snapshot, same Post.
    grown = _payload()
    grown["items"][0]["metrics"] = {"likes": 200, "reposts": 45, "impressions": 15000}
    await client.post("/api/v1/ingest/x", json=grown, headers=headers)

    async with db_sessionmaker() as session:
        assert await session.scalar(select(func.count(Post.id))) == 1
        assert await session.scalar(select(func.count(PostMetric.id))) == 2
