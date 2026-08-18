"""Live X velocity scoring — what is spiking right now (X Pulse).

Distinct from TrendScore, which measures a NEWS EVENT across RSS/HN/GitHub/Reddit. This
measures a single tweet's traction on X itself, which is the actionable signal for a tool
whose only publishing channel is X.

Every term is a saturating ratio — `min(value / cap, 1) * weight`, weights summing to 100 —
so the score is bounded, explainable, and tunable one cap at a time. The two ratio terms
are deliberately normalised against likes: a repost or a bookmark costs the reader more
than a like, so their ratio to likes measures amplification and save-worthiness rather
than raw popularity (the same asymmetry xsim's weight vector encodes).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# weight, cap
W_VELOCITY, CAP_VELOCITY = 40.0, 50_000.0  # views per hour
W_ENGAGEMENT, CAP_ENGAGEMENT = 25.0, 0.10  # (likes+reposts+replies) / views
W_REPOST, CAP_REPOST = 20.0, 0.50  # reposts / likes
W_BOOKMARK, CAP_BOOKMARK = 15.0, 0.30  # bookmarks / likes

# views/hour tiers
TIER_WARM = 1_000.0
TIER_HOT = 10_000.0

# Below this the ratios are noise, not signal.
MIN_VIEWS_FOR_RATIOS = 50


@dataclass
class Velocity:
    views_per_hour: float
    score: float  # 0-100
    tier: str  # cold | warm | hot
    age_hours: float


def _sat(value: float, cap: float, weight: float) -> float:
    if cap <= 0:
        return 0.0
    return min(value / cap, 1.0) * weight


def tier_for(views_per_hour: float) -> str:
    if views_per_hour >= TIER_HOT:
        return "hot"
    if views_per_hour >= TIER_WARM:
        return "warm"
    return "cold"


def compute_velocity(
    *,
    impressions: int | None,
    likes: int | None,
    reposts: int | None,
    replies: int | None,
    bookmarks: int | None,
    posted_at: datetime | None,
    now: datetime | None = None,
) -> Velocity:
    now = now or datetime.now(UTC)
    if posted_at is None:
        return Velocity(0.0, 0.0, "cold", 0.0)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)

    # Floor the age so a just-posted tweet can't divide by ~0 and score infinite.
    age_hours = max((now - posted_at) / timedelta(hours=1), 0.1)

    views = float(impressions or 0)
    likes_f = float(likes or 0)
    vph = views / age_hours

    score = _sat(vph, CAP_VELOCITY, W_VELOCITY)

    if views >= MIN_VIEWS_FOR_RATIOS:
        engagements = likes_f + float(reposts or 0) + float(replies or 0)
        score += _sat(engagements / views, CAP_ENGAGEMENT, W_ENGAGEMENT)
    if likes_f > 0:
        score += _sat(float(reposts or 0) / likes_f, CAP_REPOST, W_REPOST)
        score += _sat(float(bookmarks or 0) / likes_f, CAP_BOOKMARK, W_BOOKMARK)

    return Velocity(
        views_per_hour=round(vph, 1),
        score=round(min(score, 100.0), 2),
        tier=tier_for(vph),
        age_hours=round(age_hours, 2),
    )


def amplification_ratios(
    *, likes: int | None, reposts: int | None, bookmarks: int | None
) -> dict[str, float | None]:
    """Did this get amplified, or merely approved?

    repost/like and bookmark/like separate "people passed it on / saved it" from "people
    tapped the cheapest button". Both are stronger learning targets than raw likes.
    """
    likes_f = float(likes or 0)
    if likes_f <= 0:
        return {"repost_ratio": None, "bookmark_ratio": None}
    return {
        "repost_ratio": round(float(reposts or 0) / likes_f, 3),
        "bookmark_ratio": round(float(bookmarks or 0) / likes_f, 3),
    }
