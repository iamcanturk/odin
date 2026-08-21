"""Posts API: approved drafts + mark-as-posted (PROJECT.md §24)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Post, ProfileSnapshot
from app.pipeline.benchmark import CORPUS_WINDOW_DAYS, latest_sightings
from app.pipeline.postmortem import post_mortem
from app.pipeline.publish import mark_posted
from app.pipeline.queue import schedule, suggest_slot
from app.schemas.api import MarkPostedRequest, PostRead


class PostUpdate(BaseModel):
    """Edit a draft before publishing (human-in-the-loop, PROJECT.md §24)."""

    text: str = Field(min_length=1, max_length=10000)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostRead])
async def list_posts(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None),
) -> list[Post]:
    stmt = select(Post).order_by(Post.created_at.desc())
    if status:
        stmt = stmt.where(Post.status == status)
    rows = await session.execute(stmt)
    return list(rows.scalars())


class ScheduleRequest(BaseModel):
    """Queue a draft. `auto` asks for your best hour; `when=null` clears the queue."""

    when: datetime | None = None
    auto: bool = False


class SlotRead(BaseModel):
    when: datetime | None = None
    hour: int | None = None
    reason: str


@router.get("/slot", response_model=SlotRead)
async def next_slot(session: AsyncSession = Depends(get_session)) -> SlotRead:
    """The next occurrence of your best posting hour, or why we can't name one."""
    s = await suggest_slot(session)
    return SlotRead(**s.__dict__)


@router.post("/{post_id}/schedule", response_model=PostRead)
async def schedule_post(
    post_id: uuid.UUID,
    payload: ScheduleRequest,
    session: AsyncSession = Depends(get_session),
) -> Post:
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "posted":
        raise HTTPException(status_code=409, detail="Already posted")

    when = payload.when
    if payload.auto:
        slot = await suggest_slot(session)
        if slot.when is None:
            raise HTTPException(status_code=409, detail=slot.reason)
        when = slot.when

    await schedule(session, post, when)
    await session.commit()
    await session.refresh(post)
    return post


class ComparisonRead(BaseModel):
    label: str
    actual: float
    reference: float | None = None
    verdict: str
    note: str


class PostMortemRead(BaseModel):
    post_id: str
    text: str
    posted_at: datetime | None = None
    hours_since_post: float | None = None
    settled: bool
    likes: int
    replies: int
    reposts: int
    impressions: int | None = None
    first_hour_likes: int | None = None
    tags: list[str] = []
    comparisons: list[ComparisonRead] = []
    lessons: list[str] = []


@router.get("/{post_id}/postmortem", response_model=PostMortemRead)
async def get_post_mortem(
    post_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PostMortemRead:
    """Why did this post do what it did — against prediction, your median, and the room."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    handles = {
        h.lower()
        for (h,) in await session.execute(select(ProfileSnapshot.handle).distinct())
        if h
    }
    corpus = await latest_sightings(
        session,
        own_handles=handles,
        cutoff=datetime.now(UTC) - timedelta(days=CORPUS_WINDOW_DAYS),
    )
    m = await post_mortem(
        session, post, corpus_likes=sorted(float(t.likes or 0) for t in corpus)
    )
    return PostMortemRead(
        **{k: v for k, v in m.__dict__.items() if k != "comparisons"},
        comparisons=[ComparisonRead(**c.__dict__) for c in m.comparisons],
    )


@router.patch("/{post_id}", response_model=PostRead)
async def update_post(
    post_id: uuid.UUID,
    payload: PostUpdate,
    session: AsyncSession = Depends(get_session),
) -> Post:
    """Edit a draft's text. Published posts are immutable (their prediction is on record)."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "posted":
        raise HTTPException(status_code=409, detail="Published posts cannot be edited")
    post.text = payload.text
    await session.commit()
    await session.refresh(post)
    return post


@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Discard a draft. Published posts are kept as performance history."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "posted":
        raise HTTPException(status_code=409, detail="Published posts cannot be deleted")
    await session.delete(post)
    await session.commit()


@router.post("/{post_id}/posted", response_model=PostRead)
async def mark_post_posted(
    post_id: uuid.UUID,
    payload: MarkPostedRequest,
    session: AsyncSession = Depends(get_session),
) -> Post:
    post = await mark_posted(session, post_id, payload.external_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    await session.commit()
    await session.refresh(post)
    return post
