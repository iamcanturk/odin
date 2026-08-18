"""Tests for human-in-the-loop editing: candidate + draft edit/delete."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.models import ContentCandidate, Event, Post
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


async def _event_with_candidate(db_sessionmaker) -> tuple[str, str]:
    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        event = Event(
            title="Something happened",
            status=EventStatus.RISING,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(event)
        await session.flush()
        cand = ContentCandidate(event_id=event.id, text="original text", angle="breaking", rank=1)
        session.add(cand)
        await session.commit()
        return str(event.id), str(cand.id)


async def test_edit_candidate_text(db_sessionmaker, client: httpx.AsyncClient) -> None:
    eid, cid = await _event_with_candidate(db_sessionmaker)
    resp = await client.patch(
        f"/api/v1/events/{eid}/candidates/{cid}", json={"text": "my edited take"}
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "my edited take"

    listing = (await client.get(f"/api/v1/events/{eid}/candidates")).json()
    assert listing[0]["text"] == "my edited take"


async def test_delete_candidate(db_sessionmaker, client: httpx.AsyncClient) -> None:
    eid, cid = await _event_with_candidate(db_sessionmaker)
    assert (await client.delete(f"/api/v1/events/{eid}/candidates/{cid}")).status_code == 204
    assert (await client.get(f"/api/v1/events/{eid}/candidates")).json() == []


async def test_edit_and_delete_draft_post(db_sessionmaker, client: httpx.AsyncClient) -> None:
    async with db_sessionmaker() as session:
        post = Post(platform="x", text="draft text", status="approved", origin="generated")
        session.add(post)
        await session.commit()
        pid = str(post.id)

    edited = await client.patch(f"/api/v1/posts/{pid}", json={"text": "polished text"})
    assert edited.status_code == 200
    assert edited.json()["text"] == "polished text"

    assert (await client.delete(f"/api/v1/posts/{pid}")).status_code == 204
    assert all(p["id"] != pid for p in (await client.get("/api/v1/posts")).json())


async def test_published_posts_are_immutable(db_sessionmaker, client: httpx.AsyncClient) -> None:
    async with db_sessionmaker() as session:
        post = Post(
            platform="x", text="already live", status="posted", origin="generated",
            external_id="123",
        )
        session.add(post)
        await session.commit()
        pid = str(post.id)

    # A published post's prediction is on record — editing or deleting would corrupt learning.
    assert (await client.patch(f"/api/v1/posts/{pid}", json={"text": "nope"})).status_code == 409
    assert (await client.delete(f"/api/v1/posts/{pid}")).status_code == 409
