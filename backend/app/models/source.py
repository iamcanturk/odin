"""Source: a registered origin of content (RSS feed, Hacker News, …)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.enums import Priority, SourceType

if TYPE_CHECKING:
    from app.models.content_item import ContentItem


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceType.RSS)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default=Priority.MEDIUM)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)

    # Source confidence heuristic (PROJECT.md §15), 0..1.
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)

    # Health / conditional-GET state (PROJECT.md §26).
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    etag: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(200), nullable=True)

    content_items: Mapped[list[ContentItem]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
