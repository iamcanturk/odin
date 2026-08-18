"""Events API: ranked list + detail with sources and items."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import ContentCandidate, ContentItem, Event, EventTopic, Source, Topic
from app.models.enums import EventStatus
from app.pipeline.content import create_candidates
from app.pipeline.publish import approve_candidate
from app.providers.factory import get_llm_provider
from app.schemas.api import (
    ApproveResponse,
    CandidateRead,
    CandidateUpdate,
    EventDetail,
    EventItem,
    EventList,
    EventSourceRef,
    EventSummary,
    PostRead,
    PredictionRead,
)

router = APIRouter(prefix="/events", tags=["events"])


async def _counts(
    session: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Return {event_id: (item_count, source_count)} for the given events."""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(
            ContentItem.event_id,
            func.count(ContentItem.id),
            func.count(func.distinct(ContentItem.source_id)),
        )
        .where(ContentItem.event_id.in_(event_ids))
        .group_by(ContentItem.event_id)
    )
    return {r[0]: (r[1], r[2]) for r in rows}


async def _source_types(
    session: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """Return {event_id: [distinct source types]} — where each opportunity comes from."""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(ContentItem.event_id, Source.type)
        .join(Source, ContentItem.source_id == Source.id)
        .where(ContentItem.event_id.in_(event_ids))
        .distinct()
    )
    out: dict[uuid.UUID, list[str]] = {}
    for event_id, stype in rows:
        out.setdefault(event_id, [])
        if stype not in out[event_id]:
            out[event_id].append(stype)
    return out


async def _matched_topics(
    session: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """Return {event_id: [matched topic names]} — why an event is relevant to the user."""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(EventTopic.event_id, Topic.name)
        .join(Topic, EventTopic.topic_id == Topic.id)
        .where(EventTopic.event_id.in_(event_ids), EventTopic.relevance > 0)
        .order_by(EventTopic.relevance.desc())
    )
    out: dict[uuid.UUID, list[str]] = {}
    for event_id, name in rows:
        out.setdefault(event_id, []).append(name)
    return out


@router.get("", response_model=EventList)
async def list_events(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    min_trend: float = Query(0.0, ge=0.0, le=100.0),
    order_by: str = Query("trend_score", pattern="^(trend_score|opportunity_score|last_seen_at)$"),
) -> EventList:
    filters = []
    if status:
        filters.append(Event.status == status)
    else:
        # Dismissed (archived) events never resurface in the default list.
        filters.append(Event.status != EventStatus.ARCHIVED)
    if min_trend > 0:
        filters.append(Event.trend_score >= min_trend)

    total = await session.scalar(select(func.count(Event.id)).where(*filters)) or 0

    order_col = {
        "trend_score": Event.trend_score,
        "opportunity_score": Event.opportunity_score,
        "last_seen_at": Event.last_seen_at,
    }[order_by]

    rows = await session.execute(
        select(Event).where(*filters).order_by(order_col.desc()).limit(limit).offset(offset)
    )
    events = list(rows.scalars())
    ids = [e.id for e in events]
    counts = await _counts(session, ids)
    stypes = await _source_types(session, ids)
    etopics = await _matched_topics(session, ids)

    items = []
    for e in events:
        item_count, source_count = counts.get(e.id, (0, 0))
        summary = EventSummary.model_validate(e)
        summary.item_count = item_count
        summary.source_count = source_count
        summary.source_types = stypes.get(e.id, [])
        summary.topics = etopics.get(e.id, [])
        items.append(summary)

    return EventList(total=total, items=items)


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(
    event_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> EventDetail:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    rows = await session.execute(
        select(ContentItem, Source)
        .join(Source, ContentItem.source_id == Source.id)
        .where(ContentItem.event_id == event_id)
        .order_by(ContentItem.published_at.desc().nullslast())
    )
    pairs = list(rows)

    detail = EventDetail.model_validate(event)
    detail.item_count = len(pairs)

    sources: dict[uuid.UUID, EventSourceRef] = {}
    items: list[EventItem] = []
    for item, src in pairs:
        # First image found across the event's items — offered as a post attachment.
        if detail.suggested_image is None:
            for m in item.media or []:
                if isinstance(m, dict) and m.get("type") == "image" and m.get("url"):
                    detail.suggested_image = str(m["url"])
                    break
        sources.setdefault(
            src.id,
            EventSourceRef(id=src.id, name=src.name, type=src.type, confidence=src.confidence),
        )
        items.append(
            EventItem(
                id=item.id,
                title=item.title,
                url=item.url,
                source_name=src.name,
                published_at=item.published_at,
            )
        )
    detail.sources = list(sources.values())
    detail.source_count = len(sources)
    detail.items = items[:50]
    return detail


@router.post("/{event_id}/generate", response_model=list[CandidateRead], status_code=201)
async def generate_event_content(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    language: str = Query("", pattern="^(en|tr|)$"),
    kind: str = Query("", pattern="^(breaking|contrarian|technical|educational|question|)$"),
    length: str = Query("short", pattern="^(short|long|story|thread)$"),
) -> list[ContentCandidate]:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    lang = language or get_settings().content_language
    angles = [kind] if kind else None
    return await create_candidates(
        session, event, get_llm_provider(), language=lang, angles=angles, length=length
    )


@router.post("/{event_id}/dismiss", status_code=200)
async def dismiss_event(
    event_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Mark an event as not interesting — archives it so it drops off the console."""
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = EventStatus.ARCHIVED
    await session.commit()
    return {"id": str(event_id), "status": event.status.value}


@router.get("/{event_id}/candidates", response_model=list[CandidateRead])
async def list_event_candidates(
    event_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ContentCandidate]:
    rows = await session.execute(
        select(ContentCandidate)
        .where(ContentCandidate.event_id == event_id)
        .order_by(ContentCandidate.created_at.desc(), ContentCandidate.rank)
    )
    return list(rows.scalars())


@router.patch("/{event_id}/candidates/{candidate_id}", response_model=CandidateRead)
async def update_event_candidate(
    event_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: CandidateUpdate,
    session: AsyncSession = Depends(get_session),
) -> ContentCandidate:
    """Tweak a generated draft before approving it (human-in-the-loop, PROJECT.md §24)."""
    candidate = await session.get(ContentCandidate, candidate_id)
    if candidate is None or candidate.event_id != event_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.text = payload.text
    await session.commit()
    await session.refresh(candidate)
    return candidate


@router.delete("/{event_id}/candidates/{candidate_id}", status_code=204)
async def delete_event_candidate(
    event_id: uuid.UUID,
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Discard a generated draft you don't want to keep."""
    candidate = await session.get(ContentCandidate, candidate_id)
    if candidate is None or candidate.event_id != event_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
    await session.delete(candidate)
    await session.commit()


@router.post("/{event_id}/candidates/{candidate_id}/approve", response_model=ApproveResponse)
async def approve_event_candidate(
    event_id: uuid.UUID,
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ApproveResponse:
    candidate = await session.get(ContentCandidate, candidate_id)
    if candidate is None or candidate.event_id != event_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
    post, prediction = await approve_candidate(session, candidate)
    await session.commit()
    await session.refresh(post)
    await session.refresh(prediction)
    return ApproveResponse(
        post=PostRead.model_validate(post),
        prediction=PredictionRead.model_validate(prediction),
    )
