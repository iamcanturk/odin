"""Import the user's own posts + metric snapshots from inbound X items (PROJECT.md §12)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Post, PostMetric
from app.pipeline.publish import mark_posted
from app.schemas.x import XIngestItem

log = get_logger("odin.posts")

_METRIC_FIELDS = ("impressions", "likes", "replies", "reposts", "bookmarks")

# Browsing your own profile fires repeated scans; without a floor an unchanged reading
# would be stored every few seconds. Just under the 5-minute sampling cadence.
MIN_SNAPSHOT_GAP = timedelta(minutes=4)


def normalise_for_match(text: str) -> str:
    """Compare drafts to published tweets ignoring cosmetic differences.

    X mangles what you paste: it trims, collapses whitespace, and appends a t.co link when
    media or a URL is attached. Matching on the raw string would almost never hit.
    """
    t = re.sub(r"https?://\S+", " ", text or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def match_ratio(a: str, b: str) -> float:
    """0-1 similarity between a draft and a published tweet, on normalised text."""
    na, nb = normalise_for_match(a), normalise_for_match(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


async def link_posted_draft(
    session: AsyncSession, item: XIngestItem, *, threshold: float = 0.86
) -> Post | None:
    """Find the approved draft this tweet came from and link it automatically.

    Removes the manual "paste the tweet id" step: the extension sees your new tweet
    anyway, so if it closely matches a draft you approved, that draft IS this tweet.
    Deliberately conservative — a wrong link would attach a prediction to the wrong post
    and corrupt the learning loop, so anything below the threshold is left alone.
    """
    if not item.text or not item.id:
        return None

    candidates = list(
        (
            await session.execute(
                select(Post).where(
                    Post.origin == "generated",
                    Post.status == "approved",
                    Post.external_id.is_(None),
                )
            )
        ).scalars()
    )
    if not candidates:
        return None

    best, best_score = None, 0.0
    for post in candidates:
        score = match_ratio(post.text, item.text)
        if score > best_score:
            best, best_score = post, score

    if best is None or best_score < threshold:
        return None

    linked = await mark_posted(session, best.id, item.id)
    if linked is not None:
        log.info(
            "posts.auto_linked",
            post_id=str(best.id),
            tweet=item.id,
            score=round(best_score, 3),
        )
    return linked


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
