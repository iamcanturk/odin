"""Association tables: Event↔Source and Event↔Topic (PROJECT.md §37)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.source import Source
    from app.models.topic import Topic


class EventSource(Base):
    __tablename__ = "event_sources"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="event_sources")
    source: Mapped[Source] = relationship()


class EventTopic(Base):
    __tablename__ = "event_topics"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    relevance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    event: Mapped[Event] = relationship(back_populates="event_topics")
    topic: Mapped[Topic] = relationship(back_populates="event_topics")
