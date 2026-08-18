"""Tests for prediction-vs-actual evaluation."""

from __future__ import annotations

from app.models import Post, PostMetric, PostPrediction
from app.pipeline.evaluation import EvalItem, evaluate, mae, precision_at_k, rmse


def test_mae_rmse() -> None:
    pairs = [(10.0, 12.0), (20.0, 16.0)]  # errors 2, 4
    assert mae(pairs) == 3.0
    assert rmse(pairs) == round((((2**2) + (4**2)) / 2) ** 0.5, 3)
    assert mae([]) == 0.0


def test_precision_at_k() -> None:
    items = [
        EvalItem("a", "", 0, 100, 0, 0, viral_score=90),
        EvalItem("b", "", 0, 80, 0, 0, viral_score=80),
        EvalItem("c", "", 0, 5, 0, 0, viral_score=70),
        EvalItem("d", "", 0, 3, 0, 0, viral_score=10),
    ]
    # top-3 predicted (a,b,c) vs top-3 actual (a,b,c) -> perfect
    assert precision_at_k(items, 3) == 1.0
    assert precision_at_k(items, 9) is None  # not enough items


_seq = 0


async def _posted_with(session, *, predicted_likes: int, actual_likes: int, viral: float) -> None:
    global _seq
    _seq += 1
    post = Post(
        platform="x", text="draft", status="posted", origin="generated", external_id=f"x{_seq}"
    )
    session.add(post)
    await session.flush()
    session.add(
        PostPrediction(post_id=post.id, viral_score=viral, predicted_likes=predicted_likes)
    )
    session.add(PostMetric(post_id=post.id, likes=actual_likes))


async def test_evaluate_computes_errors(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        await _posted_with(session, predicted_likes=10, actual_likes=12, viral=80)
        await _posted_with(session, predicted_likes=20, actual_likes=16, viral=40)
        await session.commit()

        summary = await evaluate(session)
        assert summary.evaluated == 2
        assert summary.mae == 3.0  # errors 2 and 4
        assert summary.rmse > 0
        assert len(summary.items) == 2
        assert all(it.abs_error >= 0 for it in summary.items)
