"""Personal performance model: what content works for THIS user (PROJECT.md §12-13).

Deterministic, explainable aggregation of the user's historical posts + their latest
metrics, grouped by content type and by matched topic. Scores are normalized 0-100
relative to the user's best-performing category.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric, Topic
from app.pipeline.text import keywords

# Engagement weighting — replies/reposts signal more than a passive like.
W_LIKE = 1.0
W_REPLY = 3.0
W_REPOST = 2.0


@dataclass
class Category:
    category: str
    score: float
    posts: int
    avg_engagement: float


@dataclass
class PerformanceSummary:
    total_posts: int = 0
    by_type: list[Category] = field(default_factory=list)
    by_topic: list[Category] = field(default_factory=list)


def content_type_tags(text: str) -> list[str]:
    """Coarse content-type tags for a post."""
    tags: list[str] = []
    has_q = "?" in text
    has_link = "http" in text.lower()
    has_num = any(ch.isdigit() for ch in text)
    if has_q:
        tags.append("question")
    if has_link:
        tags.append("link")
    if has_num:
        tags.append("number")
    if not (has_q or has_link):
        tags.append("plain")
    return tags


def engagement(metric: PostMetric | None) -> float:
    if metric is None:
        return 0.0
    return (
        W_LIKE * (metric.likes or 0)
        + W_REPLY * (metric.replies or 0)
        + W_REPOST * (metric.reposts or 0)
    )


def _rank(buckets: dict[str, list[float]]) -> list[Category]:
    """Turn {category: [engagements]} into ranked, 0-100-normalized categories."""
    averaged = {k: (sum(v) / len(v), len(v)) for k, v in buckets.items() if v}
    if not averaged:
        return []
    top = max(avg for avg, _ in averaged.values()) or 1.0
    cats = [
        Category(
            category=k,
            score=round(100.0 * avg / top, 1),
            posts=n,
            avg_engagement=round(avg, 1),
        )
        for k, (avg, n) in averaged.items()
    ]
    cats.sort(key=lambda c: c.score, reverse=True)
    return cats


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# Below this many posts a "best time" claim is noise, not a finding.
MIN_POSTS_FOR_TIMING = 5


@dataclass
class TimeSlot:
    label: str
    key: int  # hour 0-23, or weekday 0-6
    score: float  # 0-100, relative to the user's best slot
    posts: int
    avg_engagement: float


@dataclass
class TimingSummary:
    total_posts: int = 0
    enough_data: bool = False
    min_posts: int = MIN_POSTS_FOR_TIMING
    best_hour: int | None = None
    best_day: int | None = None
    by_hour: list[TimeSlot] = field(default_factory=list)
    by_day: list[TimeSlot] = field(default_factory=list)


def _slots(buckets: dict[int, list[float]], labeller) -> list[TimeSlot]:
    averaged = {k: (sum(v) / len(v), len(v)) for k, v in buckets.items() if v}
    if not averaged:
        return []
    top = max(avg for avg, _ in averaged.values()) or 1.0
    slots = [
        TimeSlot(
            label=labeller(k),
            key=k,
            score=round(100.0 * avg / top, 1),
            posts=n,
            avg_engagement=round(avg, 1),
        )
        for k, (avg, n) in averaged.items()
    ]
    slots.sort(key=lambda s: s.key)
    return slots


async def compute_timing(session: AsyncSession) -> TimingSummary:
    """When does THIS user's audience actually engage? (PROJECT.md §10, §31)

    Uses the hour/day captured on each imported post plus its latest metric snapshot.
    Deliberately refuses to guess from a handful of posts.
    """
    posts = list((await session.execute(select(Post))).scalars())
    timed = [p for p in posts if p.hour is not None or p.day_of_week is not None]
    if len(timed) < MIN_POSTS_FOR_TIMING:
        return TimingSummary(total_posts=len(timed), enough_data=False)

    by_hour: dict[int, list[float]] = {}
    by_day: dict[int, list[float]] = {}
    for post in timed:
        latest = (
            await session.execute(
                select(PostMetric)
                .where(PostMetric.post_id == post.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        eng = engagement(latest)
        if post.hour is not None:
            by_hour.setdefault(post.hour, []).append(eng)
        if post.day_of_week is not None:
            by_day.setdefault(post.day_of_week, []).append(eng)

    hours = _slots(by_hour, lambda h: f"{h:02d}:00")
    days = _slots(by_day, lambda d: DAY_NAMES[d % 7])
    best_hour = max(hours, key=lambda s: s.avg_engagement).key if hours else None
    best_day = max(days, key=lambda s: s.avg_engagement).key if days else None

    return TimingSummary(
        total_posts=len(timed),
        enough_data=True,
        best_hour=best_hour,
        best_day=best_day,
        by_hour=hours,
        by_day=days,
    )


async def compute_performance(session: AsyncSession) -> PerformanceSummary:
    posts = list((await session.execute(select(Post))).scalars())
    if not posts:
        return PerformanceSummary()

    topics = list(
        (await session.execute(select(Topic).where(Topic.enabled.is_(True)))).scalars()
    )
    topic_kw = {t.name: {k.lower() for k in (t.keywords or [])} for t in topics}

    by_type: dict[str, list[float]] = {}
    by_topic: dict[str, list[float]] = {}

    for post in posts:
        latest = (
            await session.execute(
                select(PostMetric)
                .where(PostMetric.post_id == post.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        eng = engagement(latest)

        for tag in content_type_tags(post.text):
            by_type.setdefault(tag, []).append(eng)

        post_kw = keywords(post.text)
        for name, kws in topic_kw.items():
            if kws & post_kw:
                by_topic.setdefault(name, []).append(eng)

    return PerformanceSummary(
        total_posts=len(posts),
        by_type=_rank(by_type),
        by_topic=_rank(by_topic),
    )
