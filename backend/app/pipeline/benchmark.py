"""Your numbers against the corpus you've actually seen (PROJECT.md §13).

"3 likes" means nothing on its own. It means something against the tweets that
scrolled past you in the same niche: it can be the 20th percentile or the 70th.
The extension has collected thousands of sightings; this turns them into a ruler.

Honest caveat, surfaced in the API: this corpus is what X *chose to show you*,
which skews high. Treat it as "compared to what a good timeline looks like",
not "compared to the average tweet".
"""

from __future__ import annotations

import statistics
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ObservedTweet, Post, PostMetric

# Below this the percentiles are shaped by a handful of tweets, not a distribution.
MIN_CORPUS = 50
# Sightings older than this describe an audience that has since moved on.
CORPUS_WINDOW_DAYS = 90


@dataclass
class Distribution:
    """Where the corpus sits on one metric."""

    metric: str
    p25: float
    median: float
    p75: float
    p90: float


@dataclass
class PostRank:
    post_id: str
    text: str
    posted_at: datetime | None
    likes: int
    impressions: int | None
    like_percentile: float
    verdict: str  # below | typical | above | top


@dataclass
class BenchmarkSummary:
    corpus_size: int = 0
    enough_data: bool = False
    min_corpus: int = MIN_CORPUS
    window_days: int = CORPUS_WINDOW_DAYS
    your_posts: int = 0
    # The single number: where your median post lands in the corpus.
    your_percentile: float | None = None
    distributions: list[Distribution] = field(default_factory=list)
    posts: list[PostRank] = field(default_factory=list)
    caveat: str = (
        "Karşılaştırma, X'in sana gösterdiği tweetlere göre yapılıyor — "
        "yani ortalama tweete değil, iyi performans gösterenlere."
    )


def percentile_of(sorted_values: list[float], value: float) -> float:
    """What fraction of the corpus this value beats, 0-100."""
    if not sorted_values:
        return 0.0
    return round(100.0 * bisect_left(sorted_values, value) / len(sorted_values), 1)


def _quantiles(values: list[float]) -> tuple[float, float, float, float]:
    ordered = sorted(values)
    n = len(ordered)

    def at(fraction: float) -> float:
        return round(ordered[min(n - 1, int(fraction * n))], 1)

    return at(0.25), at(0.50), at(0.75), at(0.90)


def _verdict(pct: float) -> str:
    if pct >= 90:
        return "top"
    if pct >= 60:
        return "above"
    if pct >= 30:
        return "typical"
    return "below"


async def latest_sightings(
    session: AsyncSession, *, own_handles: set[str], cutoff: datetime
) -> list[ObservedTweet]:
    """Latest sighting per tweet — repeated views must not weight one tweet twice."""
    latest = (
        select(
            ObservedTweet.external_id,
            func.max(ObservedTweet.observed_at).label("seen"),
        )
        .where(ObservedTweet.observed_at >= cutoff, ObservedTweet.is_reply.is_(False))
        .group_by(ObservedTweet.external_id)
        .subquery()
    )
    rows = list(
        (
            await session.execute(
                select(ObservedTweet).join(
                    latest,
                    (ObservedTweet.external_id == latest.c.external_id)
                    & (ObservedTweet.observed_at == latest.c.seen),
                )
            )
        )
        .scalars()
        .unique()
    )
    return [
        r
        for r in rows
        if (r.author_handle or "").lower().lstrip("@") not in own_handles
        and r.likes is not None
    ]


async def benchmark(
    session: AsyncSession, *, own_handles: set[str] | None = None, now: datetime | None = None
) -> BenchmarkSummary:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=CORPUS_WINDOW_DAYS)
    handles = {h.lower().lstrip("@") for h in (own_handles or set())}

    corpus = await latest_sightings(session, own_handles=handles, cutoff=cutoff)
    if len(corpus) < MIN_CORPUS:
        return BenchmarkSummary(corpus_size=len(corpus), enough_data=False)

    likes = sorted(float(t.likes or 0) for t in corpus)
    impressions = [float(t.impressions) for t in corpus if t.impressions]

    distributions = [Distribution("likes", *_quantiles(likes))]
    if len(impressions) >= MIN_CORPUS // 2:
        distributions.append(Distribution("impressions", *_quantiles(impressions)))

    posts = list(
        (await session.execute(select(Post).where(Post.status == "posted"))).scalars()
    )
    ranked: list[PostRank] = []
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
        pct = percentile_of(likes, float(metric.likes))
        ranked.append(
            PostRank(
                post_id=str(post.id),
                text=post.text[:160],
                posted_at=post.posted_at,
                likes=metric.likes,
                impressions=metric.impressions,
                like_percentile=pct,
                verdict=_verdict(pct),
            )
        )

    ranked.sort(key=lambda r: r.like_percentile, reverse=True)
    return BenchmarkSummary(
        corpus_size=len(corpus),
        enough_data=True,
        your_posts=len(ranked),
        your_percentile=(
            round(statistics.median(r.like_percentile for r in ranked), 1) if ranked else None
        ),
        distributions=distributions,
        posts=ranked,
    )
