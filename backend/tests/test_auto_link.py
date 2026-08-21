"""Tests for auto-linking a published tweet back to the draft it came from."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import Post
from app.pipeline.posts import match_ratio, normalise_for_match


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


DRAFT = "Docker imajlarını küçültmenin en hızlı yolu: multi-stage build kullanmak."


def test_normalisation_ignores_what_x_changes() -> None:
    # X appends a t.co link and can alter punctuation/whitespace; none of that means
    # it's a different post.
    assert normalise_for_match("Hello,  world! https://t.co/abc") == "hello world"
    assert match_ratio(DRAFT, DRAFT + " https://t.co/xyz") > 0.99


def test_an_unrelated_tweet_does_not_match() -> None:
    assert match_ratio(DRAFT, "Bugün hava çok güzel, parkta yürüyüş yaptım.") < 0.5


async def _approved_draft(db_sessionmaker, text: str = DRAFT) -> str:
    async with db_sessionmaker() as session:
        post = Post(platform="x", text=text, status="approved", origin="generated")
        session.add(post)
        await session.commit()
        return str(post.id)


async def test_publishing_a_draft_links_it_without_pasting_an_id(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    pid = await _approved_draft(db_sessionmaker)

    resp = await client.post(
        "/api/v1/ingest/x",
        json={
            "items": [
                {
                    "id": "9001",
                    # X appended a link, as it does when media is attached.
                    "text": DRAFT + " https://t.co/abc123",
                    "author_handle": "@me",
                    "created_at": "2026-08-19T10:00:00Z",
                    "is_self": True,
                    "metrics": {"likes": 3, "impressions": 200},
                }
            ]
        },
        headers={"X-Ingest-Token": "secret"},
    )
    assert resp.status_code == 201
    assert resp.json()["auto_linked"] == 1

    async with db_sessionmaker() as session:
        post = await session.get(Post, __import__("uuid").UUID(pid))
        assert post.status == "posted"
        assert post.external_id == "9001"
        assert post.posted_at is not None  # starts the metric-sampling clock


async def test_a_different_tweet_leaves_drafts_alone(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    """A wrong link would attach a prediction to the wrong post, so be conservative."""
    pid = await _approved_draft(db_sessionmaker)

    resp = await client.post(
        "/api/v1/ingest/x",
        json={
            "items": [
                {
                    "id": "9002",
                    "text": "Tamamen alakasız bir tweet, kahve içiyorum.",
                    "author_handle": "@me",
                    "is_self": True,
                }
            ]
        },
        headers={"X-Ingest-Token": "secret"},
    )
    assert resp.json()["auto_linked"] == 0

    async with db_sessionmaker() as session:
        post = await session.get(Post, __import__("uuid").UUID(pid))
        assert post.status == "approved"  # untouched
        assert post.external_id is None
        # The unrelated tweet was still imported as one of your own posts.
        others = (await session.execute(select(Post).where(Post.external_id == "9002"))).scalars()
        assert list(others)
