"""API integration tests (skipped when the database/schema is unavailable)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app


@pytest.fixture
async def client():
    # A per-test engine, created inside this test's event loop, avoids cross-loop
    # reuse of the module-level engine. Skips cleanly when the DB isn't up/migrated.
    test_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with test_engine.connect() as conn:
            has_events = await conn.scalar(text("SELECT to_regclass('public.events')"))
    except Exception:  # noqa: BLE001
        await test_engine.dispose()
        pytest.skip("database not available")
    if has_events is None:
        await test_engine.dispose()
        pytest.skip("schema not migrated")

    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_session():
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await test_engine.dispose()


async def test_events_list_shape(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/events", params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body and isinstance(body["items"], list)
    if body["items"]:
        first = body["items"][0]
        assert {"id", "title", "trend_score", "status"} <= set(first)


async def test_event_detail_or_404(client: httpx.AsyncClient) -> None:
    listing = (await client.get("/api/v1/events", params={"limit": 1})).json()
    if listing["items"]:
        eid = listing["items"][0]["id"]
        resp = await client.get(f"/api/v1/events/{eid}")
        assert resp.status_code == 200
        assert "sources" in resp.json()
    missing = await client.get(f"/api/v1/events/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_sources_list(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_topic_crud_roundtrip(client: httpx.AsyncClient) -> None:
    name = f"pytest-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/topics", json={"name": name, "keywords": ["x", "y"], "priority": "high"}
    )
    assert created.status_code == 201
    tid = created.json()["id"]

    got = await client.get(f"/api/v1/topics/{tid}")
    assert got.status_code == 200
    assert got.json()["keywords"] == ["x", "y"]

    deleted = await client.delete(f"/api/v1/topics/{tid}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/topics/{tid}")).status_code == 404
