"""Inbound ingestion for X data collected by the browser extension (PROJECT.md §25).

No paid X API: the extension POSTs captured posts here (auth via a shared token).
Items flow through the same clustering/scoring pipeline as polled sources.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import ContentItem, Source
from app.models.enums import Priority, SourceType
from app.pipeline.posts import import_user_post
from app.schemas.x import XIngestBatch, XIngestItem, XIngestResult
from app.sources.base import compute_content_hash

router = APIRouter(prefix="/ingest", tags=["ingest"])

X_SOURCE_NAME = "X"


def _verify_token(x_ingest_token: str | None) -> None:
    configured = get_settings().ingest_token
    if not configured:
        raise HTTPException(status_code=503, detail="Inbound ingestion is not configured")
    if x_ingest_token != configured:
        raise HTTPException(status_code=401, detail="Invalid ingest token")


async def _get_or_create_x_source(session: AsyncSession) -> Source:
    source = (
        await session.execute(select(Source).where(Source.name == X_SOURCE_NAME))
    ).scalar_one_or_none()
    if source is None:
        source = Source(
            name=X_SOURCE_NAME,
            type=SourceType.X,
            category="social",
            priority=Priority.HIGH,
            confidence=0.5,
            enabled=False,  # inbound-only: the poller must not try to fetch it
        )
        session.add(source)
        await session.flush()
    return source


def _to_content_item(source_id, item: XIngestItem) -> ContentItem:
    engagement = item.metrics.model_dump(exclude_none=True) if item.metrics else {}
    return ContentItem(
        source_id=source_id,
        source_item_id=item.id,
        url=item.url,
        content_hash=compute_content_hash("x", item.id),
        title=item.text[:280] if item.text else None,
        text=item.text,
        author=item.author_handle or item.author,
        published_at=item.created_at,
        language=item.lang,
        engagement=engagement,
        item_metadata={"is_self": item.is_self, "handle": item.author_handle},
    )


@router.post("/x", response_model=XIngestResult, status_code=201)
async def ingest_x(
    batch: XIngestBatch,
    session: AsyncSession = Depends(get_session),
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
) -> XIngestResult:
    _verify_token(x_ingest_token)

    source = await _get_or_create_x_source(session)
    hashes = [compute_content_hash("x", it.id) for it in batch.items]
    existing = set()
    if hashes:
        rows = await session.execute(
            select(ContentItem.content_hash).where(ContentItem.content_hash.in_(hashes))
        )
        existing = {r[0] for r in rows}

    created: list[ContentItem] = []
    seen: set[str] = set(existing)
    for item in batch.items:
        h = compute_content_hash("x", item.id)
        if h in seen:
            continue
        seen.add(h)
        ci = _to_content_item(source.id, item)
        session.add(ci)
        created.append(ci)
    await session.flush()

    # Import the user's own posts (+ metric snapshots) for style/performance analysis.
    for item in batch.items:
        if item.is_self:
            await import_user_post(session, item)

    # Store + return immediately; the ARQ worker embeds/clusters/scores these
    # (event_id is null) within ~a minute, so the extension never blocks on the model.
    await session.commit()

    return XIngestResult(
        received=len(batch.items),
        created=len(created),
        duplicates=len(batch.items) - len(created),
        events_created=0,
    )
