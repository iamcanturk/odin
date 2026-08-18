"""ProfileSnapshot: the user's X profile stats over time (PROJECT.md §12)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import uuid_pk


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    handle: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tweets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )
