"""Prediction vs actual + evaluation metrics (PROJECT.md §33, §35).

Compares each posted post's stored prediction to its latest actual metrics. Predictions
are never mutated — this only reads. Aggregate metrics: MAE, RMSE, precision@K on ranking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric, PostPrediction


@dataclass
class EvalItem:
    post_id: str
    text: str
    predicted_likes: int
    actual_likes: int
    abs_error: int
    error_pct: float
    viral_score: float


@dataclass
class EvalSummary:
    evaluated: int = 0
    mae: float = 0.0
    rmse: float = 0.0
    precision_at_3: float | None = None
    items: list[EvalItem] = field(default_factory=list)


def mae(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return round(sum(abs(p - a) for p, a in pairs) / len(pairs), 3)


def rmse(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return round(math.sqrt(sum((p - a) ** 2 for p, a in pairs) / len(pairs)), 3)


def precision_at_k(items: list[EvalItem], k: int) -> float | None:
    """Fraction of the top-k predicted (by viral score) that are in the top-k actual (by likes)."""
    if len(items) < k:
        return None
    top_pred = {i.post_id for i in sorted(items, key=lambda x: x.viral_score, reverse=True)[:k]}
    top_actual = {i.post_id for i in sorted(items, key=lambda x: x.actual_likes, reverse=True)[:k]}
    return round(len(top_pred & top_actual) / k, 3)


async def _latest_prediction(session: AsyncSession, post_id) -> PostPrediction | None:
    return (
        await session.execute(
            select(PostPrediction)
            .where(PostPrediction.post_id == post_id)
            .order_by(PostPrediction.predicted_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_metric(session: AsyncSession, post_id) -> PostMetric | None:
    return (
        await session.execute(
            select(PostMetric)
            .where(PostMetric.post_id == post_id)
            .order_by(PostMetric.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def evaluate(session: AsyncSession) -> EvalSummary:
    posts = list(
        (await session.execute(select(Post).where(Post.status == "posted"))).scalars()
    )
    items: list[EvalItem] = []
    for post in posts:
        pred = await _latest_prediction(session, post.id)
        metric = await _latest_metric(session, post.id)
        if pred is None or metric is None or pred.predicted_likes is None or metric.likes is None:
            continue
        abs_err = abs(pred.predicted_likes - metric.likes)
        pct = round(100.0 * abs_err / metric.likes, 1) if metric.likes else 0.0
        items.append(
            EvalItem(
                post_id=str(post.id),
                text=post.text[:120],
                predicted_likes=pred.predicted_likes,
                actual_likes=metric.likes,
                abs_error=abs_err,
                error_pct=pct,
                viral_score=pred.viral_score,
            )
        )

    pairs = [(float(i.predicted_likes), float(i.actual_likes)) for i in items]
    return EvalSummary(
        evaluated=len(items),
        mae=mae(pairs),
        rmse=rmse(pairs),
        precision_at_3=precision_at_k(items, 3),
        items=items,
    )
