"""Auth API: login + session check (PROJECT.md §36)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import create_token, require_auth, verify_password
from app.schemas.api import AuthConfig, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfig)
async def auth_config(settings: Settings = Depends(get_settings)) -> AuthConfig:
    """Public: tells the frontend whether login is required."""
    return AuthConfig(auth_required=settings.auth_enabled)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, settings: Settings = Depends(get_settings)
) -> TokenResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Auth is disabled")
    if not verify_password(payload.username, payload.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenResponse(token=create_token(payload.username, settings))


@router.get("/me")
async def me(subject: str = Depends(require_auth)) -> dict[str, str]:
    return {"username": subject}
