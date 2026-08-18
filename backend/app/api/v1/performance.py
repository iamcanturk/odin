"""Personal performance API (PROJECT.md §13)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.pipeline.performance import compute_performance, compute_timing
from app.schemas.api import PerformanceSummary

router = APIRouter(prefix="/performance", tags=["performance"])


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
