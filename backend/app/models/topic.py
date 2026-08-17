"""Topic: a user-defined subject of interest with include/exclude keywords (PROJECT.md §28)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import EMBED_DIM, TimestampMixin, uuid_pk
from app.models.enums import Priority

if TYPE_CHECKING:
    from app.models.associations import EventTopic


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default=Priority.MEDIUM)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    event_topics: Mapped[list[EventTopic]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )

    # Extra metadata kept for future use (avoids reserved 'metadata' attribute name).
    extra: Mapped[dict[str, Any]] = mapped_column("extra", JSONB, nullable=False, default=dict)
