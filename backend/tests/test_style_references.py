"""Tests for style reference accounts (emulate someone else's writing style)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.pipeline.content import style_reference_hint


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


def _batch():
    return {
        "handle": "@storyteller",
        "items": [
            {
                "id": "9001",
                "text": "It was 3am when the pager went off.",
                "metrics": {"likes": 900},
            },
            {
                "id": "9002",
                "text": "Nobody tells you this about scaling.",
                "metrics": {"likes": 400},
            },
        ],
    }


async def test_style_ingest_requires_token(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/ingest/x/style", json=_batch())).status_code == 401


async def test_style_ingest_stores_and_dedupes(client: httpx.AsyncClient) -> None:
    headers = {"X-Ingest-Token": "secret"}
    first = await client.post("/api/v1/ingest/x/style", json=_batch(), headers=headers)
    assert first.status_code == 201
    assert first.json() == {"handle": "storyteller", "received": 2, "stored": 2}

    # Same tweets again -> nothing new stored.
    again = await client.post("/api/v1/ingest/x/style", json=_batch(), headers=headers)
    assert again.json()["stored"] == 0


async def test_styles_listing_and_hint(db_sessionmaker, client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/ingest/x/style", json=_batch(), headers={"X-Ingest-Token": "secret"}
    )
    styles = (await client.get("/api/v1/compose/styles")).json()
    assert styles == [{"handle": "storyteller", "samples": 2}]

    async with db_sessionmaker() as session:
        hint = await style_reference_hint(session, "@storyteller")
    assert "storyteller" in hint
    assert "3am when the pager" in hint  # highest-liked sample leads
    assert "only the style" in hint  # guards against copying content

    async with db_sessionmaker() as session:
        assert await style_reference_hint(session, "@nobody") == ""
