"""Tests for the publish workflow: predict + approve + mark-posted."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import ContentCandidate, Event, Post, PostPrediction
from app.models.enums import EventStatus
from app.pipeline.predict import DEFAULT_BASELINE_LIKES, baseline_likes, predict
from app.pipeline.publish import approve_candidate, mark_posted


def test_baseline_likes() -> None:
    assert baseline_likes([]) == float(DEFAULT_BASELINE_LIKES)
    assert baseline_likes([10, 20, 30]) == 20.0


def test_predict_scales_with_viral() -> None:
    low = predict("A neutral post", viral_score=20, opportunity_score=0, recent_likes=[100])
    high = predict("A neutral post", viral_score=90, opportunity_score=0, recent_likes=[100])
    assert high.predicted_likes > low.predicted_likes
    assert high.model_version == "predict-v2"
    assert high.predicted_impressions > high.predicted_likes


async def _make_candidate(session) -> ContentCandidate:
    event = Event(
        title="OpenAI ships GPT-X",
        status=EventStatus.TRENDING,
        first_seen_at=func.now(),
        last_seen_at=func.now(),
        trend_score=80,
        opportunity_score=70,
        personal_relevance=60,
    )
    session.add(event)
    await session.flush()
    cand = ContentCandidate(
        event_id=event.id,
        text="Hot take: the bottleneck was never intelligence.",
        angle="contrarian",
        viral_score=75,
        rank=1,
    )
    session.add(cand)
    await session.flush()
    return cand


async def test_approve_creates_post_and_immutable_prediction(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        cand = await _make_candidate(session)
        post, prediction = await approve_candidate(session, cand)
        await session.commit()

        assert post.status == "approved"
        assert post.origin == "generated"
        assert post.external_id is None
        assert post.angle == "contrarian"
        assert prediction.predicted_likes is not None
        assert prediction.viral_score == 75

        # one post, one prediction
        assert await session.scalar(select(func.count(Post.id))) == 1
        assert await session.scalar(select(func.count(PostPrediction.id))) == 1


async def test_mark_posted_sets_external_id(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        cand = await _make_candidate(session)
        post, _ = await approve_candidate(session, cand)
        await session.commit()

        updated = await mark_posted(session, post.id, "1810000000000000009")
        await session.commit()
        assert updated is not None
        assert updated.status == "posted"
        assert updated.external_id == "1810000000000000009"


def test_calibration_corrects_systematic_error() -> None:
    """When we've been under-predicting, the next prediction scales up."""
    base = predict("A neutral post", viral_score=50, opportunity_score=0, recent_likes=[100])
    corrected = predict(
        "A neutral post",
        viral_score=50,
        opportunity_score=0,
        recent_likes=[100],
        calibration=2.0,
    )
    assert corrected.predicted_likes > base.predicted_likes
    assert corrected.features["calibration"] == 2.0


def test_calibration_is_clamped_against_outliers() -> None:
    from app.pipeline.predict import CALIBRATION_MAX, CALIBRATION_MIN, clamp_calibration

    assert clamp_calibration(999.0) == CALIBRATION_MAX
    assert clamp_calibration(0.0001) == CALIBRATION_MIN
    wild = predict(
        "A neutral post", viral_score=50, opportunity_score=0,
        recent_likes=[100], calibration=999.0,
    )
    assert wild.features["calibration"] == CALIBRATION_MAX
