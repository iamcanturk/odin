"""Pydantic response/request schemas for the v1 API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Events ----


class EventSummary(ORMModel):
    id: uuid.UUID
    title: str
    summary: str | None = None
    status: str
    trend_score: float
    opportunity_score: float
    confidence_score: float
    personal_relevance: float = 0.0
    first_seen_at: datetime
    last_seen_at: datetime
    source_count: int = 0
    item_count: int = 0


class EventItem(ORMModel):
    id: uuid.UUID
    title: str | None = None
    url: str | None = None
    source_name: str | None = None
    published_at: datetime | None = None


class EventSourceRef(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    confidence: float


class EventDetail(EventSummary):
    entities: list[Any] = Field(default_factory=list)
    velocity: dict[str, Any] = Field(default_factory=dict)
    scoring_version: str | None = None
    sources: list[EventSourceRef] = Field(default_factory=list)
    items: list[EventItem] = Field(default_factory=list)


class EventList(BaseModel):
    total: int
    items: list[EventSummary]


# ---- Sources ----


class SourceRead(ORMModel):
    id: uuid.UUID
    name: str
    type: str
    url: str | None = None
    category: str | None = None
    priority: str
    enabled: bool
    poll_interval_seconds: int
    confidence: float
    last_polled_at: datetime | None = None
    last_success_at: datetime | None = None
    failure_count: int


class SourceCreate(BaseModel):
    name: str
    type: str = "rss"
    url: str | None = None
    category: str | None = None
    priority: str = "med"
    enabled: bool = True
    poll_interval_seconds: int = 900
    confidence: float = 0.6


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    priority: str | None = None
    enabled: bool | None = None
    poll_interval_seconds: int | None = None
    confidence: float | None = None


# ---- Topics ----


class TopicRead(ORMModel):
    id: uuid.UUID
    name: str
    keywords: list[str]
    exclude_keywords: list[str]
    priority: str
    enabled: bool


class TopicCreate(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    priority: str = "med"
    enabled: bool = True


class TopicUpdate(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    priority: str | None = None
    enabled: bool | None = None
