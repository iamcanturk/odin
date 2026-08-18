"""Schemas for inbound X (browser-extension) ingestion."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class XMetrics(BaseModel):
    likes: int | None = None
    replies: int | None = None
    reposts: int | None = None
    bookmarks: int | None = None
    impressions: int | None = None


class XIngestItem(BaseModel):
    id: str
    text: str
    author: str | None = None
    author_handle: str | None = None
    url: str | None = None
    created_at: datetime | None = None
    lang: str | None = None
    metrics: XMetrics | None = None
    is_self: bool = False  # authored by the ODIN user (for personal post import)


class XIngestBatch(BaseModel):
    items: list[XIngestItem] = Field(default_factory=list)


class XIngestResult(BaseModel):
    received: int
    created: int
    duplicates: int
    events_created: int


class XStyleSampleBatch(BaseModel):
    """Tweets from an account whose writing style the user wants to emulate."""

    handle: str = Field(min_length=1, max_length=120)
    items: list[XIngestItem] = Field(default_factory=list)


class XProfileIngest(BaseModel):
    handle: str = Field(min_length=1, max_length=120)
    followers: int | None = None
    following: int | None = None
    tweets: int | None = None
