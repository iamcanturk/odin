"""Profile API: the user's writing-style fingerprint (PROJECT.md §11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import ProfileSnapshot, StyleProfile
from app.pipeline.style import build_style_profile
from app.providers.factory import get_embedding_provider
from app.schemas.api import ProfileGrowth, ProfilePoint, StyleProfileRead

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/growth", response_model=ProfileGrowth)
async def profile_growth(session: AsyncSession = Depends(get_session)) -> ProfileGrowth:
    rows = list(
        (
            await session.execute(
                select(ProfileSnapshot).order_by(ProfileSnapshot.captured_at.asc())
            )
        ).scalars()
    )
    if not rows:
        return ProfileGrowth()
    first, last = rows[0], rows[-1]
    series = [
        ProfilePoint(
            captured_at=s.captured_at,
            followers=s.followers,
            following=s.following,
            tweets=s.tweets,
        )
        for s in rows
    ]
    df = (
        (last.followers - first.followers)
        if last.followers is not None and first.followers is not None
        else None
    )
    dg = (
        (last.following - first.following)
        if last.following is not None and first.following is not None
        else None
    )
    return ProfileGrowth(
        handle=last.handle,
        snapshots=len(rows),
        latest=series[-1],
        delta_followers=df,
        delta_following=dg,
        series=series,
    )


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
