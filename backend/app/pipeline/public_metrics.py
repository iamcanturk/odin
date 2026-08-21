"""Keep your own post metrics moving on days you never open X.

Until now every metric came from the browser extension, which meant the time series
froze whenever you didn't visit your profile — exactly when you most want to know
whether last night's post landed.

This closes half the gap. The syndication endpoint gives likes and replies with no
login; reposts, impressions and bookmarks still require the extension's view of the
logged-in GraphQL payloads. Rows written here are marked as partial by leaving those
fields NULL, so nothing pretends to know a number it doesn't.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric
from app.sources.x_syndication import fetch_public_metrics

# Posts older than this rarely move; polling them is spend without signal.
ACTIVE_WINDOW = timedelta(days=14)
# Don't write a new row when nothing changed — the series should show movement,
# not the polling interval.
MIN_GAP = timedelta(minutes=20)


@dataclass
class RefreshStats:
    checked: int = 0
    updated: int = 0
    missing: int = 0
    errors: list[str] = field(default_factory=list)


async def _latest(session: AsyncSession, post_id) -> PostMetric | None:
    return (
        await session.execute(
            select(PostMetric)
            .where(PostMetric.post_id == post_id)
            .order_by(PostMetric.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def refresh_public_metrics(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 40
) -> RefreshStats:
    now = now or datetime.now(UTC)
    stats = RefreshStats()

    posts = list(
        (
            await session.execute(
                select(Post)
                .where(
                    Post.external_id.is_not(None),
                    Post.platform == "x",
                    Post.posted_at.is_not(None),
                    Post.posted_at >= now - ACTIVE_WINDOW,
                )
                .order_by(Post.posted_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    if not posts:
        return stats

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for post in posts:
            stats.checked += 1
            result = await fetch_public_metrics(str(post.external_id), client=client)
            if not result.found:
                stats.missing += 1
                continue

            previous = await _latest(session, post.id)
            if previous is not None:
                captured = previous.captured_at
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=UTC)
                unchanged = (
                    previous.likes == result.likes and previous.replies == result.replies
                )
                if unchanged and now - captured < MIN_GAP:
                    continue
                if unchanged:
                    continue

            session.add(
                PostMetric(
                    post_id=post.id,
                    captured_at=now,
                    likes=result.likes,
                    replies=result.replies,
                    # Deliberately NULL: the public endpoint doesn't expose these, and
                    # a zero here would poison every ratio that reads them.
                    reposts=None,
                    impressions=None,
                    bookmarks=None,
                )
            )
            stats.updated += 1

    await session.flush()
    return stats
