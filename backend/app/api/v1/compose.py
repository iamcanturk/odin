"""Composer API: generate posts about ANY topic the user types (PROJECT.md §21).

Unlike /events/{id}/generate this needs no event — the user supplies the subject, the
format (short / long / story / thread) and the audience (technical / general).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import StyleReference
from app.pipeline.content import ANGLES, compose_freeform
from app.providers.factory import get_llm_provider

router = APIRouter(prefix="/compose", tags=["compose"])


class ComposeRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=2000)
    language: str = Field(default="", pattern="^(en|tr|)$")
    length: str = Field(default="short", pattern="^(short|long|story|thread)$")
    audience: str = Field(default="technical", pattern="^(technical|general)$")
    kind: str = Field(
        default="", pattern="^(breaking|contrarian|technical|educational|question|)$"
    )
    style_handle: str = Field(default="", max_length=120)


class ComposeDraft(BaseModel):
    text: str
    angle: str
    viral_score: float
    novelty_score: float
    risk_score: float
    rank: int


class StyleRef(BaseModel):
    handle: str
    samples: int


@router.get("/styles", response_model=list[StyleRef])
async def list_styles(session: AsyncSession = Depends(get_session)) -> list[StyleRef]:
    """Accounts the extension has sampled, available as style references."""
    rows = await session.execute(
        select(StyleReference.handle, func.count())
        .group_by(StyleReference.handle)
        .order_by(func.count().desc())
    )
    return [StyleRef(handle=h, samples=n) for h, n in rows]


@router.post("", response_model=list[ComposeDraft])
async def compose(
    payload: ComposeRequest, session: AsyncSession = Depends(get_session)
) -> list[ComposeDraft]:
    lang = payload.language or get_settings().content_language
    angles = [payload.kind] if payload.kind else None
    drafts = await compose_freeform(
        session,
        payload.topic,
        get_llm_provider(),
        language=lang,
        length=payload.length,
        audience=payload.audience,
        angles=angles,
        style_handle=payload.style_handle,
        n=min(3, len(ANGLES)),
    )
    return [
        ComposeDraft(
            text=d.text,
            angle=d.angle,
            viral_score=d.viral_score,
            novelty_score=d.novelty_score,
            risk_score=d.risk_score,
            rank=d.rank,
        )
        for d in drafts
    ]
