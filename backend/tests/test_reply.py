"""Tests for reply generation."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.pipeline.content import REPLY_ANGLES, generate_replies
from app.providers.base import LLMProvider


class _CapturingLLM(LLMProvider):
    def __init__(self) -> None:
        self.systems: list[str] = []
        self.prompts: list[str] = []

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        self.systems.append(system or "")
        self.prompts.append(prompt)
        return "A specific, concrete reply — with a dash."


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_reply_angles_are_distinct_from_post_angles(db_sessionmaker) -> None:
    from app.pipeline.content import ANGLES

    # "breaking news" makes no sense as a reply; the sets must not be interchangeable.
    assert "breaking" not in REPLY_ANGLES
    assert set(REPLY_ANGLES) != set(ANGLES)


async def test_generates_one_draft_per_angle(db_sessionmaker) -> None:
    llm = _CapturingLLM()
    async with db_sessionmaker() as session:
        drafts = await generate_replies(session, "The original post", llm)
    assert len(drafts) == len(REPLY_ANGLES)
    assert {d.angle for d in drafts} == set(REPLY_ANGLES)
    # Ranked, and em dashes stripped like everywhere else.
    assert [d.rank for d in drafts] == list(range(1, len(drafts) + 1))
    assert all("—" not in d.text for d in drafts)


async def test_parent_and_thread_context_reach_the_prompt(db_sessionmaker) -> None:
    llm = _CapturingLLM()
    async with db_sessionmaker() as session:
        await generate_replies(
            session,
            "Kubernetes is overkill for most teams",
            llm,
            parent_handle="@someone",
            thread_context="An earlier reply in the thread",
            angles=["extend"],
        )
    prompt = llm.prompts[0]
    assert "Kubernetes is overkill" in prompt
    assert "@someone" in prompt
    assert "An earlier reply in the thread" in prompt
    # No-flattery rule is enforced in the system prompt.
    assert any("flattery" in s.lower() for s in llm.systems)


async def test_reply_endpoint(client: httpx.AsyncClient, monkeypatch) -> None:
    # Stub the provider: without this the test hits the real API whenever a key is
    # configured, which makes it slow, costly and dependent on the model's judgement.
    import app.api.v1.compose as compose_api

    monkeypatch.setattr(compose_api, "get_llm_provider", lambda: _CapturingLLM())

    resp = await client.post(
        "/api/v1/compose/reply",
        json={"text": "Kubernetes is overkill for most teams", "author_handle": "@x",
              "kind": "question"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["angle"] == "question"


async def test_a_reply_with_nothing_to_add_is_dropped(db_sessionmaker) -> None:
    """The prompt tells the model to answer SKIP rather than pad; honour that."""

    class _SkipLLM(LLMProvider):
        async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
            return "SKIP"

    async with db_sessionmaker() as session:
        drafts = await generate_replies(session, "A content-free tweet", _SkipLLM())
    assert drafts == []
