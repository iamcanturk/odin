"""Tests for the browser feed relay (sources that block our server's IP)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import ContentItem, Source
from app.models.enums import Priority, SourceType

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>r/programming</title>
  <entry>
    <title>A post about compilers</title>
    <link href="https://reddit.com/r/programming/a"/>
    <id>t3_aaa</id>
    <updated>2026-08-19T09:00:00+00:00</updated>
    <content type="html">&lt;p&gt;Body text&lt;/p&gt;</content>
  </entry>
  <entry>
    <title>Another post</title>
    <link href="https://reddit.com/r/programming/b"/>
    <id>t3_bbb</id>
    <updated>2026-08-19T09:05:00+00:00</updated>
    <content type="html">&lt;p&gt;More text&lt;/p&gt;</content>
  </entry>
</feed>
"""


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


async def _seed_source(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        session.add(
            Source(
                name="Reddit r/programming", type=SourceType.RSS,
                url="https://www.reddit.com/r/programming/.rss", category="technology",
                priority=Priority.MEDIUM, confidence=0.7, enabled=False,
            )
        )
        await session.commit()


async def test_relay_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ingest/feed", json={"source_name": "Reddit r/programming", "body": ATOM}
    )
    assert resp.status_code == 401


async def test_relay_parses_and_dedupes(db_sessionmaker, client: httpx.AsyncClient) -> None:
    await _seed_source(db_sessionmaker)
    headers = {"X-Ingest-Token": "secret"}
    payload = {"source_name": "Reddit r/programming", "body": ATOM}

    first = await client.post("/api/v1/ingest/feed", json=payload, headers=headers)
    assert first.status_code == 201
    assert first.json()["created"] == 2

    # Same body again: parsed, but nothing new (content_hash dedup, as with polled feeds).
    second = await client.post("/api/v1/ingest/feed", json=payload, headers=headers)
    assert second.json() == {"source": "Reddit r/programming", "received": 2, "created": 0}

    async with db_sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(ContentItem)) == 2
        titles = {t for (t,) in await session.execute(select(ContentItem.title))}
        assert "A post about compilers" in titles
        # HTML is stripped, exactly like a normally-polled feed.
        texts = [t for (t,) in await session.execute(select(ContentItem.text)) if t]
        assert all("<p>" not in t for t in texts)


async def test_relay_rejects_an_unknown_source(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ingest/feed",
        json={"source_name": "Nope", "body": ATOM},
        headers={"X-Ingest-Token": "secret"},
    )
    assert resp.status_code == 404
