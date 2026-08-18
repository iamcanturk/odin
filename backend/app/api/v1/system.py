"""System API: AI cost tracking + pipeline run logs (PROJECT.md §44)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import LlmUsage, RunLog

router = APIRouter(prefix="/system", tags=["system"])


class CostBucket(BaseModel):
    purpose: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class RunLogRead(BaseModel):
    kind: str
    sources_polled: int
    items_created: int
    events_created: int
    errors: list[str]
    created_at: datetime


class SystemStatus(BaseModel):
    cost_total_usd: float
    cost_30d_usd: float
    calls_total: int
    tokens_total: int
    by_purpose: list[CostBucket]
    recent_runs: list[RunLogRead]


@router.get("", response_model=SystemStatus)
async def system_status(session: AsyncSession = Depends(get_session)) -> SystemStatus:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    total_cost = (
        await session.execute(select(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)))
    ).scalar_one()
    cost_30d = (
        await session.execute(
            select(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)).where(
                LlmUsage.created_at >= cutoff
            )
        )
    ).scalar_one()
    calls_total = (
        await session.execute(select(func.count()).select_from(LlmUsage))
    ).scalar_one()
    tokens_total = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(LlmUsage.prompt_tokens + LlmUsage.completion_tokens), 0
                )
            )
        )
    ).scalar_one()

    by_purpose_rows = (
        await session.execute(
            select(
                LlmUsage.purpose,
                func.count(),
                func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
                func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
            ).group_by(LlmUsage.purpose)
        )
    ).all()
    by_purpose = [
        CostBucket(
            purpose=r[0] or "other",
            calls=r[1],
            prompt_tokens=r[2],
            completion_tokens=r[3],
            cost_usd=round(r[4], 6),
        )
        for r in by_purpose_rows
    ]

    runs = list(
        (
            await session.execute(
                select(RunLog).order_by(RunLog.created_at.desc()).limit(30)
            )
        ).scalars()
    )
    recent_runs = [
        RunLogRead(
            kind=r.kind,
            sources_polled=r.sources_polled,
            items_created=r.items_created,
            events_created=r.events_created,
            errors=list(r.errors or []),
            created_at=r.created_at,
        )
        for r in runs
    ]

    return SystemStatus(
        cost_total_usd=round(total_cost, 6),
        cost_30d_usd=round(cost_30d, 6),
        calls_total=calls_total,
        tokens_total=tokens_total,
        by_purpose=by_purpose,
        recent_runs=recent_runs,
    )
