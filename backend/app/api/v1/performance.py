"""Personal performance API (PROJECT.md §13)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import ProfileSnapshot
from app.pipeline.benchmark import benchmark
from app.pipeline.performance import compute_performance, compute_timing
from app.schemas.api import PerformanceSummary

router = APIRouter(prefix="/performance", tags=["performance"])


async def _own_handles(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(ProfileSnapshot.handle).distinct())
    return {h.lower() for (h,) in rows if h}


class DistributionRead(BaseModel):
    metric: str
    p25: float
    median: float
    p75: float
    p90: float


class PostRankRead(BaseModel):
    post_id: str
    text: str
    posted_at: datetime | None = None
    likes: int
    impressions: int | None = None
    like_percentile: float
    verdict: str


class BenchmarkRead(BaseModel):
    corpus_size: int
    enough_data: bool
    min_corpus: int
    window_days: int
    your_posts: int
    your_percentile: float | None = None
    caveat: str
    distributions: list[DistributionRead] = []
    posts: list[PostRankRead] = []


@router.get("/benchmark", response_model=BenchmarkRead)
async def get_benchmark(session: AsyncSession = Depends(get_session)) -> BenchmarkRead:
    """Your posts against the tweets that actually scrolled past you."""
    b = await benchmark(session, own_handles=await _own_handles(session))
    return BenchmarkRead(
        corpus_size=b.corpus_size,
        enough_data=b.enough_data,
        min_corpus=b.min_corpus,
        window_days=b.window_days,
        your_posts=b.your_posts,
        your_percentile=b.your_percentile,
        caveat=b.caveat,
        distributions=[DistributionRead(**d.__dict__) for d in b.distributions],
        posts=[PostRankRead(**r.__dict__) for r in b.posts],
    )


class TimeSlotRead(BaseModel):
    label: str
    key: int
    score: float
    posts: int
    avg_engagement: float


class TimingRead(BaseModel):
    total_posts: int
    enough_data: bool
    min_posts: int
    best_hour: int | None = None
    best_day: int | None = None
    by_hour: list[TimeSlotRead] = []
    by_day: list[TimeSlotRead] = []


@router.get("/timing", response_model=TimingRead)
async def get_timing(session: AsyncSession = Depends(get_session)) -> TimingRead:
    """When your audience actually engages — best hour / day from your own posts."""
    t = await compute_timing(session)
    return TimingRead(
        total_posts=t.total_posts,
        enough_data=t.enough_data,
        min_posts=t.min_posts,
        best_hour=t.best_hour,
        best_day=t.best_day,
        by_hour=[TimeSlotRead(**s.__dict__) for s in t.by_hour],
        by_day=[TimeSlotRead(**s.__dict__) for s in t.by_day],
    )


@router.get("", response_model=PerformanceSummary)
async def get_performance(session: AsyncSession = Depends(get_session)) -> PerformanceSummary:
    summary = await compute_performance(session)
    return PerformanceSummary(
        total_posts=summary.total_posts,
        by_type=[c.__dict__ for c in summary.by_type],
        by_topic=[c.__dict__ for c in summary.by_topic],
    )
