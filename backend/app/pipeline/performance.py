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
