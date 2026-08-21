"""Are you actually posting as much as you said you would? (PROJECT.md §31)

A weekly target is only useful if it's split across the days you have left. "25 this
week" tells you nothing on Thursday; "you're 9 behind, that's 3 a day for the rest of
the week" does.

Quality is measured, not assumed: a post counts toward the target regardless, but the
summary also reports how many cleared the corpus median, so 25 filler posts don't read
as a good week.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting, Post, PostMetric

WEEKLY_GOAL_KEY = "weekly_post_goal"
DEFAULT_WEEKLY_GOAL = 25
# The corpus median is the bar for "quality"; below this a post didn't land.
QUALITY_PERCENTILE = 50.0


@dataclass
class DayCount:
    day: date
    label: str
    posts: int
    is_today: bool = False
    is_future: bool = False


@dataclass
class CadenceSummary:
    goal: int = DEFAULT_WEEKLY_GOAL
    posted: int = 0
    remaining: int = 0
    days_left: int = 0
    # How many you'd need per remaining day (today included) to still hit the target.
    per_day_needed: float = 0.0
    on_track: bool = False
    # Of what you posted this week, how many beat the corpus median.
    quality_posts: int = 0
    week_start: date | None = None
    by_day: list[DayCount] = field(default_factory=list)


DAY_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


async def get_weekly_goal(session: AsyncSession) -> int:
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == WEEKLY_GOAL_KEY))
    ).scalar_one_or_none()
    if row is None:
        return DEFAULT_WEEKLY_GOAL
    value = row.value.get("value", DEFAULT_WEEKLY_GOAL)
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_WEEKLY_GOAL


async def set_weekly_goal(session: AsyncSession, goal: int) -> int:
    goal = max(1, min(200, goal))
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == WEEKLY_GOAL_KEY))
    ).scalar_one_or_none()
    if row is None:
        session.add(AppSetting(key=WEEKLY_GOAL_KEY, value={"value": goal}))
    else:
        row.value = {"value": goal}
    await session.flush()
    return goal


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def week_bounds(today: date) -> tuple[date, date]:
    """Monday-to-Sunday, the week people actually plan in."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


async def cadence(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    corpus_likes: list[float] | None = None,
) -> CadenceSummary:
    now = now or datetime.now(UTC)
    today = now.date()
    start, end = week_bounds(today)

    posts = list(
        (
            await session.execute(
                select(Post).where(
                    Post.status == "posted",
                    Post.posted_at >= _midnight(start),
                    Post.posted_at < _midnight(end + timedelta(days=1)),
                )
            )
        ).scalars()
    )

    buckets: dict[date, int] = {start + timedelta(days=i): 0 for i in range(7)}
    for post in posts:
        posted = post.posted_at
        if posted is None:
            continue
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)
        day = posted.date()
        if day in buckets:
            buckets[day] += 1

    goal = await get_weekly_goal(session)
    posted_count = len(posts)
    remaining = max(0, goal - posted_count)
    # Today still counts — you can post later tonight.
    days_left = (end - today).days + 1

    quality = 0
    if corpus_likes:
        from app.pipeline.benchmark import percentile_of

        for post in posts:
            metric = (
                await session.execute(
                    select(PostMetric)
                    .where(PostMetric.post_id == post.id)
                    .order_by(PostMetric.captured_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if metric is None or metric.likes is None:
                continue
            if percentile_of(corpus_likes, float(metric.likes)) >= QUALITY_PERCENTILE:
                quality += 1

    per_day = round(remaining / days_left, 1) if days_left > 0 else float(remaining)
    # On track = you're at least where a flat daily pace would put you by now.
    elapsed = 7 - days_left + 1
    expected_by_now = goal * elapsed / 7

    return CadenceSummary(
        goal=goal,
        posted=posted_count,
        remaining=remaining,
        days_left=days_left,
        per_day_needed=per_day,
        on_track=posted_count >= expected_by_now,
        quality_posts=quality,
        week_start=start,
        by_day=[
            DayCount(
                day=day,
                label=DAY_LABELS[i],
                posts=count,
                is_today=day == today,
                is_future=day > today,
            )
            for i, (day, count) in enumerate(sorted(buckets.items()))
        ],
    )
