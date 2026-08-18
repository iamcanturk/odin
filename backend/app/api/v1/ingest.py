"""Inbound ingestion for X data collected by the browser extension (PROJECT.md §25).

X is treated as an OUTPUT channel, not an input: we do NOT turn other people's tweets
into events. We only import the user's OWN posts (+ engagement snapshots) for style and
performance analysis, and profile-stats snapshots for follower growth. Event/opportunity
content comes from the other sources (RSS/HN/GitHub/Reddit/Google Trends).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import ProfileSnapshot, StyleReference
from app.pipeline.posts import import_user_post
from app.schemas.x import (
    XIngestBatch,
    XIngestResult,
    XProfileIngest,
    XStyleSampleBatch,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _verify_token(x_ingest_token: str | None) -> None:
    configured = get_settings().ingest_token
    if not configured:
        raise HTTPException(status_code=503, detail="Inbound ingestion is not configured")
    if x_ingest_token != configured:
        raise HTTPException(status_code=401, detail="Invalid ingest token")


@router.post("/x", response_model=XIngestResult, status_code=201)
async def ingest_x(
    batch: XIngestBatch,
    session: AsyncSession = Depends(get_session),
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
) -> XIngestResult:
    _verify_token(x_ingest_token)

    # Import only the user's own posts (+ metric snapshots). Everyone else's tweets are
    # ignored — X is not an event source.
    imported = 0
    for item in batch.items:
        if item.is_self:
            await import_user_post(session, item)
            imported += 1
    await session.commit()

    return XIngestResult(
        received=len(batch.items),
        created=imported,
        duplicates=len(batch.items) - imported,
        events_created=0,
    )


@router.post("/x/style", status_code=201)
async def ingest_x_style(
    batch: XStyleSampleBatch,
    session: AsyncSession = Depends(get_session),
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
) -> dict[str, int | str]:
    """Store tweets from an account the user wants to write like. Deduped per handle+id."""
    _verify_token(x_ingest_token)
    handle = batch.handle.lstrip("@").lower()

    ids = [it.id for it in batch.items if it.id]
    existing: set[str] = set()
    if ids:
        rows = await session.execute(
            select(StyleReference.external_id).where(
                StyleReference.handle == handle, StyleReference.external_id.in_(ids)
            )
        )
        existing = {r[0] for r in rows}

    stored = 0
    for item in batch.items:
        if not item.id or not item.text or item.id in existing:
            continue
        existing.add(item.id)
        session.add(
            StyleReference(
                handle=handle,
                external_id=item.id,
                text=item.text,
                url=item.url,
                likes=item.metrics.likes if item.metrics else None,
                reposts=item.metrics.reposts if item.metrics else None,
                posted_at=item.created_at,
            )
        )
        stored += 1
    await session.commit()
    return {"handle": handle, "received": len(batch.items), "stored": stored}


@router.post("/x/profile", status_code=201)
async def ingest_x_profile(
    payload: XProfileIngest,
    session: AsyncSession = Depends(get_session),
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
) -> dict[str, str | bool]:
    """Record a profile stats snapshot (followers/following/tweets). Deduped when unchanged."""
    _verify_token(x_ingest_token)
    handle = payload.handle.lstrip("@").lower()

    latest = (
        await session.execute(
            select(ProfileSnapshot)
            .where(ProfileSnapshot.handle == handle)
            .order_by(ProfileSnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if (
        latest is not None
        and latest.followers == payload.followers
        and latest.following == payload.following
        and latest.tweets == payload.tweets
    ):
        return {"handle": handle, "stored": False}

    session.add(
        ProfileSnapshot(
            handle=handle,
            followers=payload.followers,
            following=payload.following,
            tweets=payload.tweets,
        )
    )
    await session.commit()
    return {"handle": handle, "stored": True}
