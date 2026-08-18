"""Import the user's own posts + metric snapshots from inbound X items (PROJECT.md §12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric
from app.schemas.x import XIngestItem

_METRIC_FIELDS = ("impressions", "likes", "replies", "reposts", "bookmarks")

# Browsing your own profile fires repeated scans; without a floor an unchanged reading
# would be stored every few seconds. Just under the 5-minute sampling cadence.
MIN_SNAPSHOT_GAP = timedelta(minutes=4)


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

    latest = (
        await session.execute(
            select(PostMetric)
            .where(PostMetric.post_id == post.id)
            .order_by(PostMetric.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Append when the values changed, OR when enough time has passed that this counts as a
    # new point on the curve. A flat reading is real data ("still 42 likes at T+30m"), and
    # it's also what tells the scheduler this post was checked — without it, posts_due
    # would see no recent sample and re-poll forever.
    if latest is not None:
        unchanged = all(getattr(latest, f) == snapshot[f] for f in _METRIC_FIELDS)
        captured = latest.captured_at
        if captured is not None and captured.tzinfo is None:
            captured = captured.replace(tzinfo=UTC)
        too_soon = captured is not None and (datetime.now(UTC) - captured) < MIN_SNAPSHOT_GAP
        if unchanged and too_soon:
            return post

    session.add(PostMetric(post_id=post.id, **snapshot))
    return post
