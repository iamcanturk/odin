"""A reminder queue for drafts (PROJECT.md §24, §31).

ODIN never posts for you — publishing goes through X's intent URL and you press the
button. So a "schedule" here can only mean one honest thing: hold the draft until the
hour your audience is actually awake, then tell you.

The best hour comes from compute_timing(), which refuses to name one without enough
evidence per bucket. When it refuses, so does this: you get the draft queued at a time
you chose, not a time we invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, Post
from app.pipeline.performance import compute_timing

REMINDER = "post_due"
# A reminder that fires a day late is noise; drop it rather than nag.
REMINDER_GRACE = timedelta(hours=12)


@dataclass
class SlotSuggestion:
    when: datetime | None
    hour: int | None
    reason: str


async def suggest_slot(
    session: AsyncSession, *, now: datetime | None = None
) -> SlotSuggestion:
    """The next occurrence of your best hour — or an honest refusal."""
    now = now or datetime.now(UTC)
    timing = await compute_timing(session)
    if not timing.enough_data or timing.best_hour is None:
        return SlotSuggestion(
            when=None,
            hour=None,
            reason=(
                f"En iyi saati söyleyecek kadar veri yok "
                f"(saat başına en az {timing.min_posts_per_bucket} gönderi gerekiyor)."
            ),
        )

    slot = now.replace(hour=timing.best_hour, minute=0, second=0, microsecond=0)
    if slot <= now:
        slot += timedelta(days=1)
    return SlotSuggestion(
        when=slot,
        hour=timing.best_hour,
        reason=f"{timing.best_hour:02d}:00 senin en iyi saatin.",
    )


async def schedule(
    session: AsyncSession, post: Post, when: datetime | None, *, now: datetime | None = None
) -> Post:
    """Queue a draft for a time, or clear it when `when` is None."""
    now = now or datetime.now(UTC)
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    post.scheduled_for = when
    # Re-scheduling means the old reminder no longer applies.
    post.reminded_at = None
    await session.flush()
    return post


async def due_reminders(
    session: AsyncSession, *, now: datetime | None = None
) -> list[Notification]:
    """Turn every queued draft whose time has come into one notification."""
    now = now or datetime.now(UTC)
    rows = list(
        (
            await session.execute(
                select(Post).where(
                    Post.scheduled_for.is_not(None),
                    Post.scheduled_for <= now,
                    Post.scheduled_for >= now - REMINDER_GRACE,
                    Post.reminded_at.is_(None),
                    Post.status != "posted",
                )
            )
        ).scalars()
    )

    created: list[Notification] = []
    for post in rows:
        notification = Notification(
            type=REMINDER,
            severity="info",
            title="Paylaşma zamanı",
            body=post.text[:280],
            event_id=post.event_id,
        )
        session.add(notification)
        post.reminded_at = now
        created.append(notification)

    if created:
        await session.flush()
    return created
