"""Publish workflow: approve a candidate → Post (draft) + immutable prediction.

Human-in-the-loop (PROJECT.md §24): ODIN never auto-publishes. Approval records the
decision and a prediction; actual posting is done by the user (manual / extension),
then linked back via the X post id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentCandidate, Event, Post, PostMetric, PostPrediction
from app.pipeline.evaluation import current_calibration
from app.pipeline.predict import predict


async def _recent_user_likes(session: AsyncSession, limit: int = 30) -> list[int]:
    rows = await session.execute(
        select(PostMetric.likes)
        .join(Post, PostMetric.post_id == Post.id)
        .where(Post.origin == "imported")
        .order_by(PostMetric.captured_at.desc())
        .limit(limit)
    )
    return [r[0] for r in rows if r[0] is not None]


async def approve_candidate(
    session: AsyncSession, candidate: ContentCandidate
) -> tuple[Post, PostPrediction]:
    """Create an approved draft Post from a candidate + store its prediction."""
    event = await session.get(Event, candidate.event_id)
    opportunity = event.opportunity_score if event else 0.0
    personal = (event.personal_relevance / 100.0) if event else 0.0

    post = Post(
        platform="x",
        external_id=None,
        text=candidate.text,
        status="approved",
        origin="generated",
        angle=candidate.angle,
        event_id=candidate.event_id,
        contains_link="http" in candidate.text,
    )
    session.add(post)
    await session.flush()

    # Fold in how wrong past predictions were, so the model self-corrects (§33).
    calibration, impressions_per_like = await current_calibration(session)
    p = predict(
        candidate.text,
        viral_score=candidate.viral_score,
        opportunity_score=opportunity,
        recent_likes=await _recent_user_likes(session),
        personal_fit=personal,
        calibration=calibration,
        impressions_per_like=impressions_per_like,
    )
    prediction = PostPrediction(
        post_id=post.id,
        model_version=p.model_version,
        scoring_version=p.scoring_version,
        algorithm_version=p.algorithm_version,
        viral_score=p.viral_score,
        x_simulation=p.x_simulation,
        opportunity_score=p.opportunity_score,
        predicted_impressions=p.predicted_impressions,
        predicted_likes=p.predicted_likes,
        predicted_replies=p.predicted_replies,
        predicted_reposts=p.predicted_reposts,
        features=p.features,
    )
    session.add(prediction)
    return post, prediction


async def mark_posted(session: AsyncSession, post_id: uuid.UUID, external_id: str) -> Post | None:
    """Link a draft to the tweet it became.

    The extension usually imported that same tweet already (as one of the user's own
    posts), so a row with this external_id can exist. Merging beats failing: the draft
    holds the PREDICTION and the import holds the ACTUAL metrics — the feedback loop only
    works when both live on one post.
    """
    post = await session.get(Post, post_id)
    if post is None:
        return None

    twin = (
        await session.execute(
            select(Post).where(
                Post.platform == post.platform,
                Post.external_id == external_id,
                Post.id != post.id,
            )
        )
    ).scalar_one_or_none()

    if twin is not None:
        # Move the imported metrics onto the draft, then drop the duplicate.
        await session.execute(
            update(PostMetric).where(PostMetric.post_id == twin.id).values(post_id=post.id)
        )
        if twin.posted_at and not post.posted_at:
            post.posted_at = twin.posted_at
            post.hour = twin.hour
            post.day_of_week = twin.day_of_week
        twin.external_id = None  # free the unique key before we claim it
        await session.flush()
        await session.delete(twin)
        await session.flush()

    post.external_id = external_id
    post.status = "posted"
    if post.posted_at is None:
        # Starts the metric-sampling clock — without this the post is never tracked.
        now = datetime.now(UTC)
        post.posted_at = now
        post.hour = now.hour
        post.day_of_week = now.weekday()
    return post
