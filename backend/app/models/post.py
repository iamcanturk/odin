"""User's own posts + time-series metrics (PROJECT.md §12).

Historical metrics are NEVER overwritten — each capture appends a PostMetric snapshot.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Post(TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_post_platform_extid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="x")
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    author_handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contains_link: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    followers_at_post: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metrics: Mapped[list[PostMetric]] = relationship(
        back_populates="post", cascade="all, delete-orphan", order_by="PostMetric.captured_at"
    )


class PostMetric(Base):
    __tablename__ = "post_metrics"

    id: Mapped[uuid.UUID] = uuid_pk()
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reposts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bookmarks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    post: Mapped[Post] = relationship(back_populates="metrics")
