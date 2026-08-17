"""ContentItem: normalized unit of content collected from any source (PROJECT.md §5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import EMBED_DIM, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.source import Source


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = uuid_pk()

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # id of the item within its source (feed guid, HN id, …)
    source_item_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Stable dedup key (hash of source + source_item_id/url). Unique across all items.
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    media: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    engagement: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # 'metadata' is reserved on Declarative classes -> attribute item_metadata, column "metadata".
    item_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    source: Mapped[Source] = relationship(back_populates="content_items")
    event: Mapped[Event | None] = relationship(back_populates="content_items")
