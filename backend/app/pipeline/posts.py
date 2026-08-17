"""Import the user's own posts + metric snapshots from inbound X items (PROJECT.md §12)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric
from app.schemas.x import XIngestItem

_METRIC_FIELDS = ("impressions", "likes", "replies", "reposts", "bookmarks")


def _contains_link(item: XIngestItem) -> bool:
    return bool(item.url) or (bool(item.text) and "http" in item.text)


async def import_user_post(
    session: AsyncSession, item: XIngestItem, *, platform: str = "x"
) -> Post:
    """Upsert a Post by (platform, external_id) and append a metric snapshot if it changed."""
    post = (
        await session.execute(
            select(Post).where(Post.platform == platform, Post.external_id == item.id)
        )
    ).scalar_one_or_none()

    if post is None:
        post = Post(
            platform=platform,
            external_id=item.id,
            text=item.text,
            url=item.url,
            author_handle=item.author_handle,
            posted_at=item.created_at,
            contains_link=_contains_link(item),
            hour=item.created_at.hour if item.created_at else None,
            day_of_week=item.created_at.weekday() if item.created_at else None,
        )
        session.add(post)
        await session.flush()

    if item.metrics is None:
        return post

    snapshot = {f: getattr(item.metrics, f) for f in _METRIC_FIELDS}
    if all(v is None for v in snapshot.values()):
        return post

    # Append only when values differ from the latest snapshot (idempotent when unchanged).
    latest = (
        await session.execute(
            select(PostMetric)
            .where(PostMetric.post_id == post.id)
            .order_by(PostMetric.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is not None and all(getattr(latest, f) == snapshot[f] for f in _METRIC_FIELDS):
        return post

    session.add(PostMetric(post_id=post.id, **snapshot))
    return post
