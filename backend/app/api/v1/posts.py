"""Posts API: approved drafts + mark-as-posted (PROJECT.md §24)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Post
from app.pipeline.publish import mark_posted
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
