"""Sources API: register / manage content sources (PROJECT.md §27)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import ContentItem, Source
from app.pipeline.ingest import IngestStats, poll_source
from app.schemas.api import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[Source]:
    rows = await session.execute(select(Source).order_by(Source.name))
    return list(rows.scalars())


class SourceItem(BaseModel):
    """One article a source brought in — what you actually came to read."""

    id: uuid.UUID
    title: str | None = None
    # The article's own opening. 757 of 901 items carry text and none of it was ever
    # returned, so every card in the feed rendered as a bare headline.
    summary: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    image: str | None = None
    event_id: uuid.UUID | None = None


class DiscoverItem(SourceItem):
    source_name: str
    source_category: str | None = None


# Enough to judge whether it's worth opening, not so much that the card becomes a page.
EXCERPT_CHARS = 400


def _excerpt(text: str | None) -> str | None:
    """Collapse an article's opening into a card-sized lede."""
    if not text:
        return None
    flat = " ".join(text.split())
    if len(flat) <= EXCERPT_CHARS:
        return flat or None
    # Cut on a word boundary so the ellipsis doesn't land mid-word.
    return flat[:EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"


class PollResult(BaseModel):
    """What one on-demand fetch actually produced."""

    source: str
    fetched: int
    errors: list[str] = []


@router.post("/{source_id}/poll", response_model=PollResult)
async def poll_one(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PollResult:
    """Fetch a single source right now.

    The 15-minute cron polls everything at once, which is useless when you want to see
    what Reddit or Pinterest has *this second*. Items still go through the normal
    clustering pass afterwards; this only pulls them in.
    """
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    stats = IngestStats()
    created = await poll_source(session, source, stats)
    await session.commit()
    return PollResult(source=source.name, fetched=len(created), errors=stats.errors)


@router.get("/discover", response_model=list[DiscoverItem])
async def discover(
    session: AsyncSession = Depends(get_session),
    category: str = Query("", max_length=64),
    source_id: uuid.UUID | None = Query(None),
    with_media: bool = Query(False),
    limit: int = Query(60, ge=1, le=200),
) -> list[DiscoverItem]:
    """Browse raw incoming content, by source or category, images included.

    The console shows CLUSTERED events, which is right for spotting opportunities but
    hides where anything came from — there was no way to just look at what Reddit or
    Pinterest brought in, or to see the images at all.
    """
    stmt = (
        select(ContentItem, Source)
        .join(Source, ContentItem.source_id == Source.id)
        .order_by(ContentItem.published_at.desc().nullslast())
        .limit(limit)
    )
    if source_id is not None:
        stmt = stmt.where(ContentItem.source_id == source_id)
    if category.strip():
        stmt = stmt.where(Source.category == category.strip())
    if with_media:
        stmt = stmt.where(ContentItem.media != [])

    out: list[DiscoverItem] = []
    for item, src in await session.execute(stmt):
        image = next(
            (
                str(m["url"])
                for m in (item.media or [])
                if isinstance(m, dict) and m.get("type") == "image" and m.get("url")
            ),
            None,
        )
        out.append(
            DiscoverItem(
                id=item.id,
                title=item.title,
                summary=_excerpt(item.text),
                url=item.url,
                published_at=item.published_at,
                image=image,
                event_id=item.event_id,
                source_name=src.name,
                source_category=src.category,
            )
        )
    return out


@router.get("/{source_id}/items", response_model=list[SourceItem])
async def source_items(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
) -> list[SourceItem]:
    """The latest headlines from one source.

    The sources page showed health but never the content, so there was no way to see what
    Reddit or Pinterest had actually brought in.
    """
    rows = list(
        (
            await session.execute(
                select(ContentItem)
                .where(ContentItem.source_id == source_id)
                .order_by(ContentItem.published_at.desc().nullslast())
                .limit(limit)
            )
        ).scalars()
    )
    out: list[SourceItem] = []
    for item in rows:
        image = next(
            (
                str(m["url"])
                for m in (item.media or [])
                if isinstance(m, dict) and m.get("type") == "image" and m.get("url")
            ),
            None,
        )
        out.append(
            SourceItem(
                id=item.id,
                title=item.title,
                summary=_excerpt(item.text),
                url=item.url,
                published_at=item.published_at,
                image=image,
                event_id=item.event_id,
            )
        )
    return out


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
