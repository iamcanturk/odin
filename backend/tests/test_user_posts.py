"""Tests for user post + metric import (isolated DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import Post, PostMetric
from app.pipeline.posts import import_user_post
from app.schemas.x import XIngestItem, XMetrics


def _item(**kw) -> XIngestItem:
    base = dict(
        id="900",
        text="My hot take on AI agents http://x.com",
        author_handle="@me",
        created_at=datetime(2026, 8, 18, 14, 0, tzinfo=UTC),
        is_self=True,
    )
    base.update(kw)
    return XIngestItem(**base)


async def test_import_creates_post_and_metric(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        await import_user_post(session, _item(metrics=XMetrics(likes=10, replies=2)))
        await session.commit()

        post = (await session.execute(select(Post))).scalar_one()
        assert post.external_id == "900"
        assert post.contains_link is True  # text has a link
        assert post.hour == 14
        assert post.day_of_week in range(7)
        metrics = (await session.execute(select(PostMetric))).scalars().all()
        assert len(metrics) == 1
        assert metrics[0].likes == 10


async def test_reimport_same_metrics_is_idempotent(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        await import_user_post(session, _item(metrics=XMetrics(likes=10)))
        await session.commit()
        await import_user_post(session, _item(metrics=XMetrics(likes=10)))
        await session.commit()

        assert await session.scalar(select(func.count(Post.id))) == 1
        # unchanged metrics -> no new snapshot
        assert await session.scalar(select(func.count(PostMetric.id))) == 1


async def test_changed_metrics_append_snapshot(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        await import_user_post(session, _item(metrics=XMetrics(likes=10)))
        await session.commit()
        await import_user_post(session, _item(metrics=XMetrics(likes=25, reposts=4)))
        await session.commit()

        assert await session.scalar(select(func.count(Post.id))) == 1
        # metrics changed -> a second time-series snapshot is appended
        assert await session.scalar(select(func.count(PostMetric.id))) == 2
