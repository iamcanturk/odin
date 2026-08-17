"""StyleProfile: a fingerprint of the user's writing style (PROJECT.md §11)."""

from __future__ import annotations

import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import EMBED_DIM, TimestampMixin, uuid_pk


class StyleProfile(TimestampMixin, Base):
    __tablename__ = "style_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Single-user for now; keyed so multi-user can be added later.
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default="default")
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Centroid embedding of the user's most successful posts.
    centroid: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
