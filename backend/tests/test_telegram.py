"""Tests for the Telegram push channel and inbound webhook."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import unquote

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import Post
from app.providers.telegram import intent_url

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def telegram_settings():
    """Configure Telegram, then put the cached settings back."""
    settings = get_settings()
    before = (
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_webhook_secret,
    )
    settings.telegram_bot_token = "test-token"
    settings.telegram_chat_id = "4242"
    settings.telegram_webhook_secret = "s3cret"
    yield settings
    (
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_webhook_secret,
    ) = before


def test_the_post_link_is_x_intent_not_an_api_call():
    """ODIN has no X write credentials — the button can only open the composer."""
    url = intent_url("merhaba dünya")
    assert url.startswith("https://x.com/intent/post?text=")
    assert "merhaba dünya" in unquote(url)


def test_a_source_url_rides_along_in_the_body():
    assert "https://example.com" in unquote(intent_url("look", "https://example.com"))


# ---- inbound webhook ----


async def test_the_webhook_rejects_a_bad_secret(client, telegram_settings):
    r = await client.post(
        "/api/v1/telegram/webhook",
        json={"message": {"chat": {"id": 4242}, "text": "hi"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert r.status_code == 403


async def test_the_webhook_rejects_a_foreign_chat(client, telegram_settings):
    """A valid secret in the wrong chat is still the wrong chat."""
    r = await client.post(
        "/api/v1/telegram/webhook",
        json={"message": {"chat": {"id": 9999}, "text": "hi"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
    )
    assert r.status_code == 403


async def test_a_message_becomes_a_draft(client, telegram_settings, db_sessionmaker):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda **kw: original(transport=transport, **kw)
    try:
        r = await client.post(
            "/api/v1/telegram/webhook",
            json={"message": {"chat": {"id": 4242}, "text": "pgvector notu"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
        )
    finally:
        httpx.AsyncClient = original

    assert r.status_code == 200
    assert r.json()["action"] == "draft"
    async with db_sessionmaker() as session:
        from sqlalchemy import select

        post = (await session.execute(select(Post))).scalar_one()
    assert post.text == "pgvector notu"
    assert post.status == "draft"
    assert post.angle == "telegram"
