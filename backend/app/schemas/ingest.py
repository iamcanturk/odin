"""Schemas for the ingestion layer: normalized items and fetch results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedItem(BaseModel):
    """A source item mapped onto the canonical ContentItem shape (PROJECT.md §5)."""

    source_item_id: str | None = None
    url: str | None = None
    title: str | None = None
    text: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    media: list[Any] = Field(default_factory=list)
    engagement: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class FetchResult(BaseModel):
    """Outcome of a single source poll."""

    items: list[NormalizedItem] = Field(default_factory=list)
    # Conditional-GET state to persist back onto the Source for the next poll.
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    status: str = "ok"
    error: str | None = None
