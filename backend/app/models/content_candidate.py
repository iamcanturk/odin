"""ContentCandidate: an AI-generated post candidate for an event (PROJECT.md §21)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event


class ContentCandidate(Base):
    __tablename__ = "content_candidates"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="x")

    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    personal_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    viral_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    source_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="content-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    event: Mapped[Event] = relationship()
