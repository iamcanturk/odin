"""Profile API: the user's writing-style fingerprint (PROJECT.md §11)."""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Post, PostMetric, ProfileSnapshot, StyleProfile
from app.pipeline.style import build_style_profile
from app.pipeline.velocity import amplification_ratios
from app.providers.factory import get_embedding_provider, get_llm_provider
from app.schemas.api import (
    ImportedTweet,
    MetricPoint,
    ProfileGrowth,
    ProfilePoint,
    StyleProfileRead,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/tweets", response_model=list[ImportedTweet])
async def imported_tweets(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> list[ImportedTweet]:
    """The user's own tweets (newest first) with their latest metric snapshot.

    Anything that actually exists on X counts — both tweets the extension imported and
    drafts you published from ODIN. Filtering to origin='imported' hid your own published
    drafts from this list.
    """
    posts = list(
        (
            await session.execute(
                select(Post)
                .where(Post.external_id.is_not(None))
                .order_by(Post.posted_at.desc().nulls_last(), Post.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    out: list[ImportedTweet] = []
    for p in posts:
        snapshots = list(
            (
                await session.execute(
                    select(PostMetric)
                    .where(PostMetric.post_id == p.id)
                    .order_by(PostMetric.captured_at.asc())
                )
            ).scalars()
        )
        latest = snapshots[-1] if snapshots else None
        posted = p.posted_at
        if posted is not None and posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)
        history = []
        for m in snapshots:
            captured = m.captured_at
            if captured is not None and captured.tzinfo is None:
                captured = captured.replace(tzinfo=UTC)
            history.append(
                MetricPoint(
                    captured_at=captured,
                    minutes_after_post=(
                        int((captured - posted).total_seconds() // 60)
                        if posted and captured
                        else None
                    ),
                    likes=m.likes,
                    reposts=m.reposts,
                    replies=m.replies,
                    impressions=m.impressions,
                )
            )
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
                history=history,
                **amplification_ratios(
                    likes=latest.likes if latest else None,
                    reposts=latest.reposts if latest else None,
                    bookmarks=latest.bookmarks if latest else None,
                ),
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
    profile = await build_style_profile(
        session, get_embedding_provider(), llm=get_llm_provider()
    )
    await session.commit()
    await session.refresh(profile)
    return profile
