"""Tests for OpportunityScore v1."""

from __future__ import annotations

from app.pipeline.opportunity import (
    OPPORTUNITY_VERSION,
    OpportunityInputs,
    compute_opportunity,
)


def test_version_tag() -> None:
    assert compute_opportunity(OpportunityInputs()).scoring_version == OPPORTUNITY_VERSION


def test_personal_relevance_raises_score() -> None:
    low = compute_opportunity(OpportunityInputs(trend_score=60, personal_relevance=10))
    high = compute_opportunity(OpportunityInputs(trend_score=60, personal_relevance=90))
    assert high.opportunity_score > low.opportunity_score


def test_time_sensitivity_from_freshness_and_acceleration() -> None:
    fresh = compute_opportunity(OpportunityInputs(age_hours=1, acceleration=0.8))
    stale = compute_opportunity(OpportunityInputs(age_hours=100, acceleration=0.0))
    assert fresh.time_sensitivity > stale.time_sensitivity
    assert fresh.opportunity_score > stale.opportunity_score


def test_source_confidence_matters() -> None:
    trusted = compute_opportunity(OpportunityInputs(source_confidence=0.95))
    shady = compute_opportunity(OpportunityInputs(source_confidence=0.25))
    assert trusted.opportunity_score > shady.opportunity_score


def test_low_competition_decreases_with_more_sources() -> None:
    few = compute_opportunity(OpportunityInputs(source_count=1))
    many = compute_opportunity(OpportunityInputs(source_count=12))
    assert few.low_competition > many.low_competition


def test_score_bounded() -> None:
    maxed = compute_opportunity(
        OpportunityInputs(
            trend_score=100,
            personal_relevance=100,
            age_hours=0,
            acceleration=1.0,
            source_confidence=1.0,
            source_count=1,
            content_gap=1.0,
        )
    )
    assert 0.0 <= maxed.opportunity_score <= 100.0
