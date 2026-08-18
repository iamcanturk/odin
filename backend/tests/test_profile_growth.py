"""Tests for X profile snapshots + growth (isolated DB)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import ProfileSnapshot


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


async def test_profile_snapshot_ingest_and_dedup(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    headers = {"X-Ingest-Token": "secret"}
    r1 = await client.post(
        "/api/v1/ingest/x/profile",
        json={"handle": "@me", "followers": 100, "following": 50, "tweets": 200},
        headers=headers,
    )
    assert r1.status_code == 201 and r1.json()["stored"] is True

    # Same values -> deduped (not stored).
    r2 = await client.post(
        "/api/v1/ingest/x/profile",
        json={"handle": "@me", "followers": 100, "following": 50, "tweets": 200},
        headers=headers,
    )
    assert r2.json()["stored"] is False

    # Changed -> stored.
    r3 = await client.post(
        "/api/v1/ingest/x/profile",
        json={"handle": "@me", "followers": 130, "following": 52, "tweets": 205},
        headers=headers,
    )
    assert r3.json()["stored"] is True

    async with db_sessionmaker() as session:
        assert await session.scalar(select(func.count(ProfileSnapshot.id))) == 2


async def test_profile_growth_deltas(client: httpx.AsyncClient) -> None:
    headers = {"X-Ingest-Token": "secret"}
    await client.post(
        "/api/v1/ingest/x/profile",
        json={"handle": "@me", "followers": 100, "following": 50},
        headers=headers,
    )
    await client.post(
        "/api/v1/ingest/x/profile",
        json={"handle": "@me", "followers": 140, "following": 48},
        headers=headers,
    )
    growth = (await client.get("/api/v1/profile/growth")).json()
    assert growth["snapshots"] == 2
    assert growth["latest"]["followers"] == 140
    assert growth["delta_followers"] == 40  # 140 - 100
    assert growth["delta_following"] == -2


async def test_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/ingest/x/profile", json={"handle": "@me", "followers": 1})
    assert resp.status_code == 401


async def test_imported_tweets_lists_own_posts_with_metrics(
    client: httpx.AsyncClient,
) -> None:
    headers = {"X-Ingest-Token": "secret"}
    await client.post(
        "/api/v1/ingest/x",
        json={
            "items": [
                {
                    "id": "5001",
                    "text": "my own tweet",
                    "author_handle": "@me",
                    "metrics": {"likes": 42, "reposts": 7, "impressions": 3000},
                    "is_self": True,
                },
                {"id": "5002", "text": "someone else", "author_handle": "@other"},
            ]
        },
        headers=headers,
    )
    tweets = (await client.get("/api/v1/profile/tweets")).json()
    assert len(tweets) == 1  # only the imported own post
    assert tweets[0]["text"] == "my own tweet"
    assert tweets[0]["likes"] == 42
    assert tweets[0]["impressions"] == 3000


async def test_imported_tweets_include_metric_history(client: httpx.AsyncClient) -> None:
    """The history field must always be present — the profile page calls .filter() on it."""
    headers = {"X-Ingest-Token": "secret"}
    payload = {
        "items": [
            {
                "id": "6001",
                "text": "tracked tweet",
                "author_handle": "@me",
                "created_at": "2026-08-18T10:00:00Z",
                "metrics": {"likes": 5, "impressions": 100},
                "is_self": True,
            }
        ]
    }
    await client.post("/api/v1/ingest/x", json=payload, headers=headers)

    tweets = (await client.get("/api/v1/profile/tweets")).json()
    assert len(tweets) == 1
    tw = tweets[0]
    assert "history" in tw, "the profile page does .filter() on history; it must be sent"
    assert len(tw["history"]) == 1
    point = tw["history"][0]
    assert point["impressions"] == 100
    # Position on the first-hour curve.
    assert point["minutes_after_post"] is not None
