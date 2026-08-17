"""Event: canonical real-world event clustered from many ContentItems (PROJECT.md §5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import EMBED_DIM, TimestampMixin, uuid_pk
from app.models.enums import EventStatus

if TYPE_CHECKING:
    from app.models.associations import EventSource, EventTopic
    from app.models.content_item import ContentItem


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EventStatus.DISCOVERED, index=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    velocity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    engagement: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Normalized 0..100 scores (PROJECT.md §9, §14, §15).
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scoring_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Cluster centroid embedding — used to match new items to this event.
    centroid: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    content_items: Mapped[list[ContentItem]] = relationship(back_populates="event")
    event_sources: Mapped[list[EventSource]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    event_topics: Mapped[list[EventTopic]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
