"""Tests for event categorisation + filtering."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.models import ContentItem, Event, Source
from app.models.enums import EventStatus, Priority, SourceType
from app.pipeline.ingest import apply_categories


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _event_from(db_sessionmaker, specs: list[tuple[str, float]]) -> str:
    """specs = [(source category, confidence)] — one content item per source."""
    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        event = Event(
            title="An event", status=EventStatus.RISING, first_seen_at=now, last_seen_at=now
        )
        session.add(event)
        await session.flush()
        tag = _uuid.uuid4().hex[:8]  # content_hash and source name are unique
        for i, (category, confidence) in enumerate(specs):
            src = Source(
                name=f"src-{category}-{i}-{tag}", type=SourceType.RSS, url=f"https://e/{tag}/{i}",
                category=category, priority=Priority.MEDIUM, confidence=confidence,
            )
            session.add(src)
            await session.flush()
            session.add(
                ContentItem(
                    source_id=src.id, event_id=event.id, content_hash=f"h{tag}{i}", title="t"
                )
            )
        await session.commit()
        await apply_categories(session, {event})
        await session.commit()
        return str(event.id)


async def test_category_follows_the_dominant_source(db_sessionmaker) -> None:
    eid = await _event_from(db_sessionmaker, [("security", 0.9), ("security", 0.8), ("ai", 0.5)])
    async with db_sessionmaker() as session:
        assert (await session.get(Event, _uuid.UUID(eid))).category == "security"


async def test_ties_break_toward_the_more_trusted_source(db_sessionmaker) -> None:
    # One source each, so confidence decides.
    eid = await _event_from(db_sessionmaker, [("ai", 0.95), ("technology", 0.4)])
    async with db_sessionmaker() as session:
        assert (await session.get(Event, _uuid.UUID(eid))).category == "ai"


async def test_events_can_be_filtered_by_category(
    db_sessionmaker, client: httpx.AsyncClient
) -> None:
    await _event_from(db_sessionmaker, [("security", 0.9)])
    await _event_from(db_sessionmaker, [("ai", 0.9)])

    everything = (await client.get("/api/v1/events")).json()
    assert everything["total"] == 2

    only_ai = (await client.get("/api/v1/events", params={"category": "ai"})).json()
    assert only_ai["total"] == 1
    assert only_ai["items"][0]["category"] == "ai"
