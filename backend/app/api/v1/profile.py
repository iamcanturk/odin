"""Profile API: the user's writing-style fingerprint (PROJECT.md §11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Post, PostMetric, ProfileSnapshot, StyleProfile
from app.pipeline.style import build_style_profile
from app.providers.factory import get_embedding_provider
from app.schemas.api import ImportedTweet, ProfileGrowth, ProfilePoint, StyleProfileRead

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/tweets", response_model=list[ImportedTweet])
async def imported_tweets(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> list[ImportedTweet]:
    """The user's own imported tweets (newest first) with their latest metric snapshot."""
    posts = list(
        (
            await session.execute(
                select(Post)
                .where(Post.origin == "imported")
                .order_by(Post.posted_at.desc().nulls_last(), Post.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    out: list[ImportedTweet] = []
    for p in posts:
        latest = (
            await session.execute(
                select(PostMetric)
                .where(PostMetric.post_id == p.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(
            ImportedTweet(
                id=p.id,
                external_id=p.external_id,
                text=p.text,
                url=p.url,
                posted_at=p.posted_at,
                likes=latest.likes if latest else None,
                reposts=latest.reposts if latest else None,
                replies=latest.replies if latest else None,
                bookmarks=latest.bookmarks if latest else None,
                impressions=latest.impressions if latest else None,
            )
        )
    return out


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
