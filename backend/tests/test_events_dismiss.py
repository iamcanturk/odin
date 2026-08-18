"""Tests for dashboard filtering: min_trend + dismiss (archive)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.models import Event
from app.models.enums import EventStatus


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _mk_event(db_sessionmaker, *, title: str, trend: float) -> str:
    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        e = Event(
            title=title,
            status=EventStatus.RISING,
            first_seen_at=now,
            last_seen_at=now,
            trend_score=trend,
            opportunity_score=trend,
        )
        session.add(e)
        await session.commit()
        return str(e.id)


async def test_min_trend_filters_low(db_sessionmaker, client: httpx.AsyncClient) -> None:
    await _mk_event(db_sessionmaker, title="loud", trend=80)
    await _mk_event(db_sessionmaker, title="quiet", trend=5)

    all_titles = {e["title"] for e in (await client.get("/api/v1/events")).json()["items"]}
    assert {"loud", "quiet"} <= all_titles

    filtered = (await client.get("/api/v1/events", params={"min_trend": 20})).json()
    titles = {e["title"] for e in filtered["items"]}
    assert "loud" in titles and "quiet" not in titles


async def test_dismiss_archives_and_hides(db_sessionmaker, client: httpx.AsyncClient) -> None:
    eid = await _mk_event(db_sessionmaker, title="boring", trend=60)

    resp = await client.post(f"/api/v1/events/{eid}/dismiss")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Archived events drop out of the default list.
    titles = {e["title"] for e in (await client.get("/api/v1/events")).json()["items"]}
    assert "boring" not in titles

    # ...but are still reachable when explicitly requested by status.
    archived = (await client.get("/api/v1/events", params={"status": "archived"})).json()
    assert "boring" in {e["title"] for e in archived["items"]}


async def test_search_finds_events_by_merged_headline(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    """An article that clustered under a different event title must still be findable."""
    from app.models import ContentItem, Source
    from app.models.enums import Priority, SourceType

    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        src = Source(
            name="OpenAI", type=SourceType.RSS, url="https://example.com/f",
            category="ai", priority=Priority.HIGH, confidence=0.9,
        )
        event = Event(
            title="OpenAI institutes new safeguards after a breach",
            status=EventStatus.RISING, first_seen_at=now, last_seen_at=now,
            trend_score=40, opportunity_score=40,
        )
        session.add_all([src, event])
        await session.flush()
        session.add(
            ContentItem(
                source_id=src.id, event_id=event.id, content_hash="h1",
                title="Pacing model development in an era of cyber-critical capabilities",
            )
        )
        await session.commit()

    # Searching the buried headline finds the parent event...
    found = (await client.get("/api/v1/events", params={"q": "cyber-critical"})).json()
    assert len(found["items"]) == 1
    ev = found["items"][0]
    # ...and the merged headline is surfaced so you can tell what's inside.
    assert "Pacing model development in an era of cyber-critical capabilities" in ev["headlines"]

    # A term in neither the title nor any headline matches nothing.
    assert (await client.get("/api/v1/events", params={"q": "zzzznope"})).json()["items"] == []
