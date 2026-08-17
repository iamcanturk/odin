"""OpportunityScore v1 (PROJECT.md §14) — "should THIS user talk about this NOW?".

Distinct from TrendScore ("is this topic growing?"). Deterministic + explainable +
versioned. Combines trend momentum, personal relevance, time sensitivity, source
confidence, content gap (placeholder) and low competition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentItem, Event, Source

OPPORTUNITY_VERSION = "opp-v1"

W_TREND = 0.30
W_PERSONAL = 0.30
W_TIME = 0.15
W_CONFIDENCE = 0.10
W_CONTENT_GAP = 0.10
W_COMPETITION = 0.05

FRESH_WINDOW_HOURS = 24.0
COMPETITION_TARGET = 6  # more distinct sources => more competition => lower opportunity


@dataclass
class OpportunityInputs:
    trend_score: float = 0.0  # 0-100
    personal_relevance: float = 0.0  # 0-100
    age_hours: float = 0.0
    acceleration: float = 0.0  # 0-1 (from trend components)
    source_confidence: float = 0.6  # 0-1
    source_count: int = 1
    content_gap: float = 0.5  # 0-1 placeholder until real gap detection (§22)


@dataclass
class OpportunityResult:
    opportunity_score: float = 0.0
    time_sensitivity: float = 0.0
    low_competition: float = 0.0
    scoring_version: str = OPPORTUNITY_VERSION
    components: dict[str, float] = field(default_factory=dict)


def _time_sensitivity(age_hours: float, acceleration: float) -> float:
    freshness = max(0.0, 1.0 - age_hours / FRESH_WINDOW_HOURS)
    return 0.5 * freshness + 0.5 * max(0.0, min(1.0, acceleration))


def compute_opportunity(inp: OpportunityInputs) -> OpportunityResult:
    trend = max(0.0, min(1.0, inp.trend_score / 100.0))
    personal = max(0.0, min(1.0, inp.personal_relevance / 100.0))
    time_sensitivity = _time_sensitivity(inp.age_hours, inp.acceleration)
    confidence = max(0.0, min(1.0, inp.source_confidence))
    content_gap = max(0.0, min(1.0, inp.content_gap))
    low_competition = 1.0 - min(1.0, inp.source_count / COMPETITION_TARGET)

    components = {
        "trend": trend,
        "personal_relevance": personal,
        "time_sensitivity": time_sensitivity,
        "source_confidence": confidence,
        "content_gap": content_gap,
        "low_competition": low_competition,
    }
    score01 = (
        W_TREND * trend
        + W_PERSONAL * personal
        + W_TIME * time_sensitivity
        + W_CONFIDENCE * confidence
        + W_CONTENT_GAP * content_gap
        + W_COMPETITION * low_competition
    )
    return OpportunityResult(
        opportunity_score=round(100.0 * score01, 2),
        time_sensitivity=time_sensitivity,
        low_competition=low_competition,
        components=components,
    )


async def apply_opportunity(
    session: AsyncSession, events: list[Event], *, now
) -> None:
    """Compute + store opportunity_score and confidence_score for each event."""
    for event in events:
        row = (
            await session.execute(
                select(
                    func.avg(Source.confidence),
                    func.count(func.distinct(Source.id)),
                )
                .select_from(ContentItem)
                .join(Source, ContentItem.source_id == Source.id)
                .where(ContentItem.event_id == event.id)
            )
        ).one()
        avg_conf = float(row[0]) if row[0] is not None else 0.6
        source_count = int(row[1] or 1)

        acceleration = float((event.velocity or {}).get("acceleration", 0.0))
        age_hours = (now - event.first_seen_at).total_seconds() / 3600

        result = compute_opportunity(
            OpportunityInputs(
                trend_score=event.trend_score,
                personal_relevance=event.personal_relevance,
                age_hours=age_hours,
                acceleration=acceleration,
                source_confidence=avg_conf,
                source_count=source_count,
            )
        )
        event.opportunity_score = result.opportunity_score
        event.confidence_score = round(100.0 * avg_conf, 2)
