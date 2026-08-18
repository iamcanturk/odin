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


class CandidateRead(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID
    text: str
    angle: str
    platform: str
    trend_score: float
    personal_score: float
    viral_score: float
    source_confidence: float
    novelty_score: float
    risk_score: float
    rank: int
    model_version: str


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


# ---- Style profile ----


class StyleProfileRead(ORMModel):
    key: str
    post_count: int
    features: dict[str, Any]
    summary: str | None = None
    updated_at: datetime


# ---- Tweet tester ----


class TesterRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class TesterResponse(BaseModel):
    viral_potential: float
    x_simulation: float
    personal_fit: float
    trend_fit: float
    novelty: float
    reply_potential: float
    bookmark_potential: float
    negative_risk: float
    probabilities: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    scoring_version: str
    disclaimer: str


# ---- Publish workflow ----


class PredictionRead(ORMModel):
    id: uuid.UUID
    predicted_at: datetime
    model_version: str
    viral_score: float
    x_simulation: float
    opportunity_score: float
    predicted_impressions: int | None = None
    predicted_likes: int | None = None
    predicted_replies: int | None = None
    predicted_reposts: int | None = None


class PostRead(ORMModel):
    id: uuid.UUID
    platform: str
    external_id: str | None = None
    text: str
    status: str
    origin: str
    angle: str | None = None
    event_id: uuid.UUID | None = None
    created_at: datetime


class ApproveResponse(BaseModel):
    post: PostRead
    prediction: PredictionRead


class MarkPostedRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=128)


# ---- Evaluation ----


class EvaluationItem(BaseModel):
    post_id: str
    text: str
    predicted_likes: int
    actual_likes: int
    abs_error: int
    error_pct: float
    viral_score: float


class EvaluationSummary(BaseModel):
    evaluated: int
    mae: float
    rmse: float
    precision_at_3: float | None = None
    items: list[EvaluationItem]


# ---- Notifications ----


class NotificationRead(ORMModel):
    id: uuid.UUID
    type: str
    severity: str
    title: str
    body: str | None = None
    event_id: uuid.UUID | None = None
    read: bool
    created_at: datetime
