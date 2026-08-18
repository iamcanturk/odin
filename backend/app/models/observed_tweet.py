"""Tweets seen while browsing X — the corpus behind X Pulse (velocity) and calibration.

These are other people's posts, captured from the GraphQL responses the browser already
receives. They are NOT events and never become ODIN content; they exist to answer "what is
spiking on X right now" and to give the scoring model real (text -> engagement) pairs
beyond the user's own small post history.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import uuid_pk


class ObservedTweet(Base):
    __tablename__ = "observed_tweets"
    __table_args__ = (
        # One row per (tweet, sighting) so repeated views become a time series for free.
        UniqueConstraint("external_id", "observed_at", name="uq_observed_tweet_sighting"),
        Index("ix_observed_tweets_velocity", "posted_at", "impressions"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_handle: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lang: Mapped[str | None] = mapped_column(String(16), nullable=True)

    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reposts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bookmarks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
