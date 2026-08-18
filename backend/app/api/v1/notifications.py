"""Notifications API (PROJECT.md §32)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Notification
from app.schemas.api import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    session: AsyncSession = Depends(get_session),
    unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
) -> list[Notification]:
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if unread:
        stmt = stmt.where(Notification.read.is_(False))
    rows = await session.execute(stmt)
    return list(rows.scalars())


@router.get("/unread-count", response_model=int)
async def unread_count(session: AsyncSession = Depends(get_session)) -> int:
    return (
        await session.scalar(
            select(func.count(Notification.id)).where(Notification.read.is_(False))
        )
        or 0
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Notification:
    note = await session.get(Notification, notification_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    note.read = True
    await session.commit()
    await session.refresh(note)
    return note
