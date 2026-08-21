"""Pydantic response/request schemas for the v1 API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----


class AuthConfig(BaseModel):
    auth_required: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"


# ---- Events ----


class EventSummary(ORMModel):
    id: uuid.UUID
    title: str
    title_local: str | None = None
    category: str | None = None
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
    source_types: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    headlines: list[str] = Field(default_factory=list)
    # First image found across the event's items, so the feed isn't a wall of text.
    image: str | None = None


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
    suggested_image: str | None = None  # a source image to attach to a post
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


class RepeatMatch(BaseModel):
    """A past post that already made this point."""

    post_id: str
    text: str
    similarity: float
    days_ago: int | None = None


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
    repeats: list[RepeatMatch] = Field(default_factory=list)


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
    scheduled_for: datetime | None = None
    created_at: datetime


class CandidateUpdate(BaseModel):
    """Edit a generated candidate before approving it (PROJECT.md §24)."""

    text: str = Field(min_length=1, max_length=10000)


class MetricPoint(BaseModel):
    captured_at: datetime
    minutes_after_post: int | None = None
    likes: int | None = None
    reposts: int | None = None
    replies: int | None = None
    impressions: int | None = None


class ImportedTweet(BaseModel):
    """The user's own imported tweet + its latest engagement snapshot."""

    id: uuid.UUID
    external_id: str | None = None
    text: str
    url: str | None = None
    posted_at: datetime | None = None
    likes: int | None = None
    reposts: int | None = None
    replies: int | None = None
    bookmarks: int | None = None
    impressions: int | None = None
    # Did it get amplified, or merely approved? Both are stronger learning targets than
    # raw likes: a repost or a save costs the reader more than a tap.
    repost_ratio: float | None = None
    bookmark_ratio: float | None = None
    history: list[MetricPoint] = Field(default_factory=list)


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


class MetricErrorRead(BaseModel):
    metric: str
    evaluated: int
    mae: float
    bias: str


class EvaluationSummary(BaseModel):
    evaluated: int
    mae: float
    rmse: float
    precision_at_3: float | None = None
    calibration: float = 1.0
    bias: str = "none"
    impressions_per_like: float | None = None
    reliable: bool = False
    min_for_reliable: int = 10
    calibration_clamped: bool = False
    by_metric: list[MetricErrorRead] = Field(default_factory=list)
    items: list[EvaluationItem]


# ---- Notifications ----


class ProfilePoint(BaseModel):
    captured_at: datetime
    followers: int | None = None
    following: int | None = None
    tweets: int | None = None


class ProfileGrowth(BaseModel):
    handle: str | None = None
    snapshots: int = 0
    latest: ProfilePoint | None = None
    delta_followers: int | None = None  # since the first snapshot
    delta_following: int | None = None
    series: list[ProfilePoint] = Field(default_factory=list)


class PerformanceCategory(BaseModel):
    category: str
    score: float
    posts: int
    avg_engagement: float


class PerformanceSummary(BaseModel):
    total_posts: int
    by_type: list[PerformanceCategory]
    by_topic: list[PerformanceCategory]


class NotificationRead(ORMModel):
    id: uuid.UUID
    type: str
    severity: str
    title: str
    body: str | None = None
    event_id: uuid.UUID | None = None
    read: bool
    created_at: datetime
