"""Evaluation API: prediction vs actual summary (PROJECT.md §33, §35)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.pipeline.evaluation import evaluate
from app.schemas.api import EvaluationSummary

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("", response_model=EvaluationSummary)
async def get_evaluation(session: AsyncSession = Depends(get_session)) -> EvaluationSummary:
    summary = await evaluate(session)
    return EvaluationSummary(
        evaluated=summary.evaluated,
        mae=summary.mae,
        rmse=summary.rmse,
        precision_at_3=summary.precision_at_3,
        calibration=summary.calibration,
        bias=summary.bias,
        impressions_per_like=summary.impressions_per_like,
        items=[item.__dict__ for item in summary.items],
    )
