"""Personal performance API (PROJECT.md §13)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.pipeline.performance import compute_performance
from app.schemas.api import PerformanceSummary

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("", response_model=PerformanceSummary)
async def get_performance(session: AsyncSession = Depends(get_session)) -> PerformanceSummary:
    summary = await compute_performance(session)
    return PerformanceSummary(
        total_posts=summary.total_posts,
        by_type=[c.__dict__ for c in summary.by_type],
        by_topic=[c.__dict__ for c in summary.by_topic],
    )
