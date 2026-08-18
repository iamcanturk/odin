"""Composer API: generate posts about ANY topic the user types (PROJECT.md §21).

Unlike /events/{id}/generate this needs no event — the user supplies the subject, the
format (short / long / story / thread) and the audience (technical / general).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import ContentItem, StyleReference
from app.pipeline.content import ANGLES, compose_freeform, generate_replies, refine_text
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


class RefineRequest(BaseModel):
    """Rewrite an existing post with your own instruction."""

    text: str = Field(min_length=1, max_length=10000)
    instruction: str = Field(min_length=3, max_length=2000)
    language: str = Field(default="", pattern="^(en|tr|)$")
    length: str = Field(default="short", pattern="^(short|long|story|thread)$")
    event_id: uuid.UUID | None = None  # pull the event's sources in as context


class RefineResponse(BaseModel):
    text: str


@router.post("/refine", response_model=RefineResponse)
async def refine(
    payload: RefineRequest, session: AsyncSession = Depends(get_session)
) -> RefineResponse:
    """e.g. 'summarise this as if I read the article and it explains X'."""
    lang = payload.language or get_settings().content_language

    context = ""
    if payload.event_id is not None:
        rows = await session.execute(
            select(ContentItem.title, ContentItem.text)
            .where(ContentItem.event_id == payload.event_id)
            .limit(5)
        )
        context = "\n".join(
            f"- {' '.join(p for p in (t, x) if p)}" for t, x in rows
        ).strip()

    text = await refine_text(
        session,
        payload.text,
        payload.instruction,
        get_llm_provider(),
        language=lang,
        length=payload.length,
        context=context,
    )
    return RefineResponse(text=text)


class ReplyRequest(BaseModel):
    """Draft replies to someone else's tweet."""

    text: str = Field(min_length=1, max_length=10000)  # the post being replied to
    author_handle: str = Field(default="", max_length=120)
    thread_context: str = Field(default="", max_length=4000)
    language: str = Field(default="", pattern="^(en|tr|)$")
    kind: str = Field(default="", pattern="^(extend|counterexample|question|experience|)$")


@router.post("/reply", response_model=list[ComposeDraft])
async def reply(
    payload: ReplyRequest, session: AsyncSession = Depends(get_session)
) -> list[ComposeDraft]:
    """Replying to an accelerating post borrows its distribution — xsim rates a reply 10x a like."""
    lang = payload.language or get_settings().content_language
    drafts = await generate_replies(
        session,
        payload.text,
        get_llm_provider(),
        parent_handle=payload.author_handle,
        thread_context=payload.thread_context,
        language=lang,
        angles=[payload.kind] if payload.kind else None,
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
