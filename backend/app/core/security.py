"""Single-user authentication: password check + JWT + FastAPI guard (PROJECT.md §36)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def verify_password(username: str, password: str, settings: Settings) -> bool:
    """Constant-time check of username + password against configured credentials."""
    if not settings.auth_enabled:
        return False
    user_ok = secrets.compare_digest(username, settings.auth_username)
    pass_ok = secrets.compare_digest(password, settings.auth_password)
    return user_ok and pass_ok


def create_token(subject: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expire_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Dependency guarding protected routes.

    When auth is disabled (no password configured) everything passes — convenient for
    local dev. When enabled, a valid Bearer JWT is required.
    """
    if not settings.auth_enabled:
        return "anonymous"
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return str(payload.get("sub", "user"))
