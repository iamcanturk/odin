"""Topics API: user-defined subjects with include/exclude keywords (PROJECT.md §28)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Topic
from app.schemas.api import TopicCreate, TopicRead, TopicUpdate

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicRead])
async def list_topics(session: AsyncSession = Depends(get_session)) -> list[Topic]:
    rows = await session.execute(select(Topic).order_by(Topic.name))
    return list(rows.scalars())


@router.post("", response_model=TopicRead, status_code=201)
async def create_topic(
    payload: TopicCreate, session: AsyncSession = Depends(get_session)
) -> Topic:
    topic = Topic(**payload.model_dump())
    session.add(topic)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Topic name already exists") from exc
    await session.refresh(topic)
    return topic


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic(
    topic_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Topic:
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.patch("/{topic_id}", response_model=TopicRead)
async def update_topic(
    topic_id: uuid.UUID,
    payload: TopicUpdate,
    session: AsyncSession = Depends(get_session),
) -> Topic:
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(topic, field, value)
    await session.commit()
    await session.refresh(topic)
    return topic


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(
    topic_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    await session.delete(topic)
    await session.commit()
