"""Tests for TrendScore v1 and lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.enums import EventStatus
from app.pipeline.trend import (
    SCORING_VERSION,
    Mention,
    TrendResult,
    advance_status,
    compute_trend,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _m(minutes_before: float, source_type="rss", source_name="", engagement=0.0) -> Mention:
    return Mention(
        timestamp=NOW - timedelta(minutes=minutes_before),
        source_type=source_type,
        source_name=source_name,
        engagement=engagement,
    )


def test_rising_scores_higher_than_flat_high_volume() -> None:
    # Rising: accelerating mentions in the last two hours, across platforms.
    rising: list[Mention] = []
    for i in range(3):  # previous hour: sparse
        rising.append(_m(70 + i * 5, source_type="rss", source_name=f"rss{i}"))
    plats = ["rss", "hackernews", "reddit"]
    for i in range(14):  # recent hour: dense
        rising.append(
            _m(5 + i * 3, source_type=plats[i % 3], source_name=f"s{i % 5}", engagement=5)
        )

    # Flat but high total volume, entirely ~2 days ago -> nothing recent.
    flat = [_m(2900 + i, source_type="rss", source_name=f"src{i % 5}") for i in range(100)]

    r_rising = compute_trend(rising, now=NOW)
    r_flat = compute_trend(flat, now=NOW)

    assert r_rising.trend_score > r_flat.trend_score
    assert r_rising.velocity > 0 and r_rising.acceleration > 0
    assert r_flat.velocity == 0.0  # no recent mentions
    assert r_rising.scoring_version == SCORING_VERSION


def test_empty_is_zero() -> None:
    r = compute_trend([], now=NOW)
    assert r.trend_score == 0.0


def _result(**kw) -> TrendResult:
    base = dict(trend_score=0.0, velocity=0.0, acceleration=0.0)
    base.update(kw)
    return TrendResult(**base)


def test_status_requires_corroboration() -> None:
    s = advance_status(
        EventStatus.DISCOVERED, _result(), source_count=1, recent_count=3, age_hours=1
    )
    assert s == EventStatus.DISCOVERED


def test_status_rising_and_trending_and_saturated() -> None:
    rising = advance_status(
        EventStatus.VERIFIED,
        _result(trend_score=40, velocity=0.3, acceleration=0.5),
        source_count=3,
        recent_count=8,
        age_hours=2,
    )
    assert rising == EventStatus.RISING

    trending = advance_status(
        EventStatus.RISING,
        _result(trend_score=70, velocity=0.6, acceleration=0.4),
        source_count=4,
        recent_count=20,
        age_hours=3,
    )
    assert trending == EventStatus.TRENDING

    saturated = advance_status(
        EventStatus.TRENDING,
        _result(trend_score=75, velocity=0.7, acceleration=0.1),
        source_count=5,
        recent_count=25,
        age_hours=6,
    )
    assert saturated == EventStatus.SATURATED


def test_status_declining_then_archived() -> None:
    declining = advance_status(
        EventStatus.TRENDING, _result(), source_count=4, recent_count=0, age_hours=10
    )
    assert declining == EventStatus.DECLINING

    archived = advance_status(
        EventStatus.DECLINING, _result(), source_count=4, recent_count=0, age_hours=100
    )
    assert archived == EventStatus.ARCHIVED
