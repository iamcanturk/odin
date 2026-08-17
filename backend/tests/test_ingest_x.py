"""Tests for the inbound X ingestion endpoint (isolated DB)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import ContentItem, Source


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
                "text": "OpenAI just shipped GPT-X and it is wild",
                "author_handle": "@someone",
                "created_at": "2026-08-18T10:00:00Z",
                "metrics": {"likes": 120, "replies": 8, "reposts": 30},
            },
            {"id": "1002", "text": "A second unrelated post about gardening"},
        ]
    }


async def test_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/ingest/x", json=_payload())
    assert resp.status_code == 401


async def test_ingests_and_dedupes(client: httpx.AsyncClient) -> None:
    headers = {"X-Ingest-Token": "secret"}
    first = await client.post("/api/v1/ingest/x", json=_payload(), headers=headers)
    assert first.status_code == 201
    body = first.json()
    assert body["received"] == 2
    assert body["created"] == 2

    # Second POST of the same items creates nothing new (dedup on content_hash).
    second = await client.post("/api/v1/ingest/x", json=_payload(), headers=headers)
    assert second.json()["created"] == 0
    assert second.json()["duplicates"] == 2


async def test_creates_x_source_and_items(db_sessionmaker, client: httpx.AsyncClient) -> None:
    headers = {"X-Ingest-Token": "secret"}
    await client.post("/api/v1/ingest/x", json=_payload(), headers=headers)

    async with db_sessionmaker() as session:
        src = (
            await session.execute(select(Source).where(Source.name == "X"))
        ).scalar_one()
        assert src.type == "x"
        assert src.enabled is False  # inbound-only
        count = await session.scalar(select(func.count(ContentItem.id)))
        assert count == 2
