"""Tests for live X velocity scoring (X Pulse)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import ObservedTweet
from app.pipeline.velocity import amplification_ratios, compute_velocity, tier_for


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


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _v(**kw):
    base = dict(
        impressions=0, likes=0, reposts=0, replies=0, bookmarks=0,
        posted_at=NOW - timedelta(hours=1), now=NOW,
    )
    base.update(kw)
    return compute_velocity(**base)


def test_views_per_hour_is_the_core_signal() -> None:
    v = _v(impressions=20_000, posted_at=NOW - timedelta(hours=2))
    assert v.views_per_hour == 10_000.0
    assert v.tier == "hot"


def test_a_just_posted_tweet_does_not_divide_by_zero() -> None:
    # Age is floored at 0.1h, so a brand-new tweet gets a finite (if generous) rate.
    v = _v(impressions=100, posted_at=NOW)
    assert v.age_hours == 0.1
    assert v.views_per_hour == 1000.0
    assert 0.0 <= v.score <= 100.0


def test_score_is_bounded_even_for_a_monster_tweet() -> None:
    v = _v(
        impressions=50_000_000, likes=500_000, reposts=400_000,
        replies=100_000, bookmarks=200_000, posted_at=NOW - timedelta(minutes=30),
    )
    # Velocity, repost and bookmark terms all saturate (40 + 20 + 15). The engagement
    # term stays small on purpose: at 50M views a 2% engagement RATE is normal, so a
    # mega-viral tweet scores high without pinning the scale at 100.
    assert v.score == 80.0
    assert v.score <= 100.0


def test_perfect_score_needs_every_term_saturated() -> None:
    v = _v(
        impressions=100_000, likes=5_000, reposts=5_000,
        replies=5_000, bookmarks=5_000, posted_at=NOW - timedelta(hours=1),
    )
    assert v.score == 100.0


def test_amplification_beats_raw_likes() -> None:
    """Two tweets, same reach and likes — the one people reposted scores higher."""
    approved = _v(impressions=10_000, likes=500, reposts=5)
    amplified = _v(impressions=10_000, likes=500, reposts=250)
    assert amplified.score > approved.score


def test_ratios_ignored_when_there_is_no_meaningful_data() -> None:
    # No likes -> ratio terms contribute nothing rather than dividing by zero.
    quiet = _v(impressions=10, likes=0, reposts=0)
    assert quiet.score >= 0.0
    assert amplification_ratios(likes=0, reposts=3, bookmarks=1) == {
        "repost_ratio": None,
        "bookmark_ratio": None,
    }
    assert amplification_ratios(likes=100, reposts=25, bookmarks=10) == {
        "repost_ratio": 0.25,
        "bookmark_ratio": 0.1,
    }


def test_tiers() -> None:
    assert tier_for(10) == "cold"
    assert tier_for(5_000) == "warm"
    assert tier_for(50_000) == "hot"


def test_missing_post_time_scores_zero() -> None:
    assert compute_velocity(
        impressions=99_999, likes=1, reposts=1, replies=1, bookmarks=1, posted_at=None
    ).score == 0.0


async def test_observed_ingest_and_pulse_ranking(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    now = datetime.now(UTC)
    payload = {
        "items": [
            {
                "id": "a1", "text": "spiking hard", "author_handle": "@fast",
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "metrics": {"likes": 900, "reposts": 300, "replies": 100,
                            "bookmarks": 200, "impressions": 80_000},
            },
            {
                "id": "a2", "text": "quiet one", "author_handle": "@slow",
                "created_at": (now - timedelta(hours=5)).isoformat(),
                "metrics": {"likes": 2, "reposts": 0, "replies": 0,
                            "bookmarks": 0, "impressions": 40},
            },
        ]
    }
    resp = await client.post(
        "/api/v1/ingest/x/observed", json=payload, headers={"X-Ingest-Token": "secret"}
    )
    assert resp.status_code == 201
    assert resp.json()["stored"] == 2

    body = (await client.get("/api/v1/pulse")).json()
    assert body["observed"] == 2
    # Ranked by views/hour, so the spiking tweet leads.
    assert body["items"][0]["external_id"] == "a1"
    assert body["items"][0]["tier"] == "hot"

    # Filtering to hot drops the quiet one entirely.
    hot = (await client.get("/api/v1/pulse", params={"min_tier": "hot"})).json()
    assert [i["external_id"] for i in hot["items"]] == ["a1"]


async def test_repeat_sightings_build_a_series_not_duplicates(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    now = datetime.now(UTC)
    item = {
        "id": "b1", "text": "same tweet", "author_handle": "@x",
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "metrics": {"likes": 10, "impressions": 500},
    }
    headers = {"X-Ingest-Token": "secret"}
    first = await client.post("/api/v1/ingest/x/observed", json={"items": [item]}, headers=headers)
    second = await client.post("/api/v1/ingest/x/observed", json={"items": [item]}, headers=headers)
    assert first.json()["stored"] == 1
    # Same minute -> deduped rather than duplicated.
    assert second.json()["stored"] == 0

    from sqlalchemy import func, select

    async with db_sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(ObservedTweet)) == 1
