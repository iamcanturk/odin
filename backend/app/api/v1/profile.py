"""Profile API: the user's writing-style fingerprint (PROJECT.md §11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import StyleProfile
from app.pipeline.style import build_style_profile
from app.providers.factory import get_embedding_provider
from app.schemas.api import StyleProfileRead

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=StyleProfileRead)
async def get_profile(session: AsyncSession = Depends(get_session)) -> StyleProfile:
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="No style profile yet — rebuild it first")
    return profile


@router.post("/rebuild", response_model=StyleProfileRead, status_code=201)
async def rebuild_profile(session: AsyncSession = Depends(get_session)) -> StyleProfile:
    profile = await build_style_profile(session, get_embedding_provider())
    await session.commit()
    await session.refresh(profile)
    return profile
