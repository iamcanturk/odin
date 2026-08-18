"""Posts API: approved drafts + mark-as-posted (PROJECT.md §24)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Post
from app.pipeline.publish import mark_posted
from app.schemas.api import MarkPostedRequest, PostRead

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
