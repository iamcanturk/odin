"""Sources API: register / manage content sources (PROJECT.md §27)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Source
from app.schemas.api import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[Source]:
    rows = await session.execute(select(Source).order_by(Source.name))
    return list(rows.scalars())


@router.post("", response_model=SourceRead, status_code=201)
async def create_source(
    payload: SourceCreate, session: AsyncSession = Depends(get_session)
) -> Source:
    source = Source(**payload.model_dump())
    session.add(source)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Source name already exists") from exc
    await session.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Source:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> Source:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await session.commit()
    await session.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await session.delete(source)
    await session.commit()
