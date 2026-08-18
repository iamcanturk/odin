"""Metric sampling schedule for the user's own posts (PROJECT.md §12).

Engagement is front-loaded: most of a tweet's reach happens in the first hour, so that
window is sampled densely and the cadence relaxes as the post ages. The extension asks
"is anything due?" on a timer and only does work when the answer is yes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric

# (post age at most, sample at least this often) — first match wins.
SCHEDULE: tuple[tuple[timedelta, timedelta], ...] = (
    (timedelta(hours=1), timedelta(minutes=5)),
    (timedelta(hours=6), timedelta(minutes=30)),
    (timedelta(days=1), timedelta(hours=1)),
    (timedelta(days=7), timedelta(hours=6)),
)
# Older than the last bucket: stop chasing it.
MAX_TRACKING_AGE = timedelta(days=7)


def sample_interval(age: timedelta) -> timedelta | None:
    """How often a post of this age should be sampled. None = stop tracking."""
    for max_age, interval in SCHEDULE:
        if age <= max_age:
            return interval
    return None


def is_due(age: timedelta, since_last_sample: timedelta | None) -> bool:
    interval = sample_interval(age)
    if interval is None:
        return False
    if since_last_sample is None:
        return True  # never sampled
    return since_last_sample >= interval


@dataclass
class WatchItem:
    external_id: str
    age_minutes: int
    samples: int


@dataclass
class WatchStatus:
    due: bool
    tracking: int
    items: list[WatchItem]


async def posts_due(session: AsyncSession, *, now: datetime | None = None) -> WatchStatus:
    """Which of the user's posted tweets need a fresh metric sample right now."""
    now = now or datetime.now(UTC)
    cutoff = now - MAX_TRACKING_AGE

    posts = list(
        (
            await session.execute(
                select(Post).where(
                    Post.external_id.is_not(None),
                    Post.posted_at.is_not(None),
                    Post.posted_at >= cutoff,
                )
            )
        ).scalars()
    )

    items: list[WatchItem] = []
    for post in posts:
        posted_at = post.posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=UTC)
        age = now - posted_at

        rows = list(
            (
                await session.execute(
                    select(PostMetric.captured_at)
                    .where(PostMetric.post_id == post.id)
                    .order_by(PostMetric.captured_at.desc())
                )
            ).scalars()
        )
        last = rows[0] if rows else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        since = (now - last) if last else None

        if is_due(age, since):
            items.append(
                WatchItem(
                    external_id=post.external_id,
                    age_minutes=int(age.total_seconds() // 60),
                    samples=len(rows),
                )
            )

    return WatchStatus(due=bool(items), tracking=len(posts), items=items)
