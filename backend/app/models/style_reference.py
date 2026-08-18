"""StyleReference: tweets from accounts whose style the user wants to emulate.

These are NOT events and NOT the user's own posts — they are writing samples used to
steer generation ("write like @handle does"). Stored per handle, deduped by tweet id.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import uuid_pk


class StyleReference(Base):
    __tablename__ = "style_references"
    __table_args__ = (
        UniqueConstraint("handle", "external_id", name="uq_styleref_handle_extid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    handle: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reposts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )
