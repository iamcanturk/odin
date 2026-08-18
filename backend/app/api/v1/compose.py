"""Composer API: generate posts about ANY topic the user types (PROJECT.md §21).

Unlike /events/{id}/generate this needs no event — the user supplies the subject, the
format (short / long / story / thread) and the audience (technical / general).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
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


class ComposeDraft(BaseModel):
    text: str
    angle: str
    viral_score: float
    novelty_score: float
    risk_score: float
    rank: int


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
