"""TrendScore v1 + event lifecycle (PROJECT.md §7-9).

Deterministic, explainable scoring — no LLM in the numeric path (PROJECT.md §42).
Each component is normalized to [0, 1] and combined with fixed weights; the final
score is 0-100. Weights are versioned via SCORING_VERSION so historical scores stay
comparable when the formula changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.enums import EventStatus

SCORING_VERSION = "trend-v1"

# Component weights (PROJECT.md §9). Sum = 1.0.
W_VELOCITY = 0.30
W_ACCELERATION = 0.20
W_ENGAGEMENT = 0.15
W_SPREAD = 0.15
W_NOVELTY = 0.10
W_DIVERSITY = 0.10

# Normalization constants (mentions/engagement per hour that map to ~0.5).
K_VELOCITY = 5.0
K_ACCELERATION = 5.0
K_ENGAGEMENT = 50.0
SPREAD_TARGET = 4  # distinct platforms considered "wide spread"
DIVERSITY_TARGET = 5  # distinct sources considered "diverse"
NOVELTY_WINDOW = timedelta(hours=48)
RECENT_WINDOW = timedelta(hours=1)


def _saturate(value: float, k: float) -> float:
    """Map a non-negative magnitude to [0, 1): value/(value+k)."""
    value = max(0.0, value)
    return value / (value + k) if (value + k) else 0.0


@dataclass
class Mention:
    timestamp: datetime
    source_type: str = "rss"
    source_name: str = ""
    engagement: float = 0.0


@dataclass
class TrendResult:
    trend_score: float = 0.0
    velocity: float = 0.0
    acceleration: float = 0.0
    engagement_velocity: float = 0.0
    cross_platform_spread: float = 0.0
    novelty: float = 0.0
    source_diversity: float = 0.0
    scoring_version: str = SCORING_VERSION
    components: dict[str, float] = field(default_factory=dict)


def _count_between(mentions: list[Mention], start: datetime, end: datetime) -> int:
    return sum(1 for m in mentions if start <= m.timestamp < end)


def _engagement_between(mentions: list[Mention], start: datetime, end: datetime) -> float:
    return sum(m.engagement for m in mentions if start <= m.timestamp < end)


def compute_trend(mentions: list[Mention], *, now: datetime) -> TrendResult:
    if not mentions:
        return TrendResult()

    recent_start = now - RECENT_WINDOW
    prev_start = now - 2 * RECENT_WINDOW

    recent = _count_between(mentions, recent_start, now)
    prev = _count_between(mentions, prev_start, recent_start)

    velocity = _saturate(recent, K_VELOCITY)
    # Only positive acceleration (growth) contributes to trend.
    acceleration = _saturate(recent - prev, K_ACCELERATION)
    engagement_velocity = _saturate(
        _engagement_between(mentions, recent_start, now), K_ENGAGEMENT
    )

    platforms = {m.source_type for m in mentions}
    sources = {m.source_name or m.source_type for m in mentions}
    cross_platform_spread = min(1.0, len(platforms) / SPREAD_TARGET)
    source_diversity = min(1.0, len(sources) / DIVERSITY_TARGET)

    first_seen = min(m.timestamp for m in mentions)
    age = now - first_seen
    novelty = max(0.0, 1.0 - age / NOVELTY_WINDOW)

    components = {
        "velocity": velocity,
        "acceleration": acceleration,
        "engagement_velocity": engagement_velocity,
        "cross_platform_spread": cross_platform_spread,
        "novelty": novelty,
        "source_diversity": source_diversity,
    }
    score01 = (
        W_VELOCITY * velocity
        + W_ACCELERATION * acceleration
        + W_ENGAGEMENT * engagement_velocity
        + W_SPREAD * cross_platform_spread
        + W_NOVELTY * novelty
        + W_DIVERSITY * source_diversity
    )

    return TrendResult(
        trend_score=round(100.0 * score01, 2),
        velocity=velocity,
        acceleration=acceleration,
        engagement_velocity=engagement_velocity,
        cross_platform_spread=cross_platform_spread,
        novelty=novelty,
        source_diversity=source_diversity,
        components=components,
    )


def advance_status(
    current: EventStatus | str,
    result: TrendResult,
    *,
    source_count: int,
    recent_count: int,
    age_hours: float,
) -> EventStatus:
    """Next lifecycle state (PROJECT.md §7). Monotonic-ish, driven by momentum."""
    current = EventStatus(current)

    # No recent activity: decline, then archive when old.
    if recent_count == 0:
        if age_hours >= NOVELTY_WINDOW.total_seconds() / 3600:
            return EventStatus.ARCHIVED
        if current in (EventStatus.TRENDING, EventStatus.SATURATED, EventStatus.RISING):
            return EventStatus.DECLINING
        return current if current == EventStatus.DECLINING else EventStatus.DECLINING

    # Needs corroboration before it can be more than "discovered".
    if source_count < 2:
        return EventStatus.DISCOVERED if current == EventStatus.DISCOVERED else current

    trending = result.trend_score >= 60 and result.velocity >= 0.5
    rising = result.acceleration >= 0.4

    if trending:
        # High volume but momentum stalled -> saturated.
        return EventStatus.SATURATED if result.acceleration < 0.2 else EventStatus.TRENDING
    if rising:
        return EventStatus.RISING
    return EventStatus.VERIFIED
