"""Tests for single-user auth (login, JWT, guard)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from httpx import ASGITransport

from app.core.config import Settings
from app.core.security import create_token, decode_token, verify_password
from app.main import create_app


def _settings(**kw) -> Settings:
    base = dict(auth_username="admin", auth_password="s3cret", jwt_secret="k")
    base.update(kw)
    return Settings(**base)


def test_verify_password() -> None:
    s = _settings()
    assert verify_password("admin", "s3cret", s) is True
    assert verify_password("admin", "wrong", s) is False
    assert verify_password("other", "s3cret", s) is False


def test_auth_disabled_when_no_password() -> None:
    s = _settings(auth_password="")
    assert s.auth_enabled is False
    assert verify_password("admin", "", s) is False


def test_token_roundtrip() -> None:
    s = _settings()
    token = create_token("admin", s)
    payload = decode_token(token, s)
    assert payload["sub"] == "admin"
    # wrong secret rejected
    with pytest.raises(jwt.PyJWTError):
        decode_token(token, _settings(jwt_secret="other"))


@pytest.fixture
def app_with_auth(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_password", "s3cret", raising=False)
    monkeypatch.setattr(settings, "auth_username", "admin", raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret", raising=False)
    return create_app()


async def test_protected_route_requires_token(app_with_auth) -> None:
    transport = ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # config is public
        cfg = await c.get("/api/v1/auth/config")
        assert cfg.json()["auth_required"] is True
        # protected without token -> 401
        assert (await c.get("/api/v1/events")).status_code == 401
        # bad login -> 401
        assert (
            await c.post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
        ).status_code == 401
        # good login -> token
        r = await c.post("/api/v1/auth/login", json={"username": "admin", "password": "s3cret"})
        assert r.status_code == 200
        token = r.json()["token"]
        # /auth/me with token works
        me = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["username"] == "admin"


def test_expired_token_rejected() -> None:
    s = _settings()
    expired = jwt.encode(
        {"sub": "admin", "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp())},
        s.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired, s)


async def test_open_when_auth_disabled() -> None:
    # No password configured -> auth disabled -> protected routes are open (no token).
    app = create_app()  # default settings have empty auth_password in tests
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        cfg = await c.get("/api/v1/auth/config")
        assert cfg.json()["auth_required"] is False
        # login is disabled when there's no password
        assert (
            await c.post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
        ).status_code == 400
