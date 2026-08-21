"""OpportunityScore v1 (PROJECT.md §14) — "should THIS user talk about this NOW?".

Distinct from TrendScore ("is this topic growing?"). Deterministic + explainable +
versioned. Combines trend momentum, personal relevance, time sensitivity, source
confidence, content gap (placeholder) and low competition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentItem, Event, Source, Topic
from app.models.associations import EventTopic
from app.pipeline.performance import compute_performance

OPPORTUNITY_VERSION = "opp-v1"

W_TREND = 0.30
W_PERSONAL = 0.30
W_TIME = 0.15
W_CONFIDENCE = 0.10
W_CONTENT_GAP = 0.10
W_COMPETITION = 0.05

FRESH_WINDOW_HOURS = 24.0

# Range for the personal-performance multiplier. Deliberately narrow: performance data is
# thin, so it should tilt the ranking, not dominate it.
PERF_MIN, PERF_MAX = 0.80, 1.25
COMPETITION_TARGET = 6  # more distinct sources => more competition => lower opportunity
GAP_SPREAD_TARGET = 4  # sources covering an event for it to count as "everyone talking"
GAP_DEPTH_K = 300  # chars; items much shorter than this read as shallow


def content_gap(source_count: int, avg_item_len: float) -> float:
    """Content gap (PROJECT.md §22): high when many sources cover an event shallowly.

    everyone talking (spread) + little depth (short items) => opportunity to explain better.
    """
    if avg_item_len <= 0:
        return 0.0  # no text to assess depth
    spread = min(1.0, source_count / GAP_SPREAD_TARGET)
    depth = avg_item_len / (avg_item_len + GAP_DEPTH_K)
    shallowness = 1.0 - depth
    return round(max(0.0, min(1.0, spread * shallowness)), 3)


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


async def _matched_topic_names(
    session: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not event_ids:
        return {}
    rows = await session.execute(
        select(EventTopic.event_id, Topic.name)
        .join(Topic, EventTopic.topic_id == Topic.id)
        .where(EventTopic.event_id.in_(event_ids), EventTopic.relevance > 0)
    )
    out: dict[uuid.UUID, list[str]] = {}
    for event_id, name in rows:
        out.setdefault(event_id, []).append(name.lower())
    return out


async def topic_performance_multipliers(session: AsyncSession) -> dict[str, float]:
    """How well YOU actually do on each topic, as a multiplier on personal relevance.

    ODIN measured per-topic performance but never used it: an event about something you
    reliably do well on ranked exactly like one about a topic that always flops. Scores
    are normalised 0-100 against your best topic, mapped to 0.8x-1.25x so a weak topic is
    demoted rather than erased — one bad topic shouldn't be permanently silenced.
    """
    summary = await compute_performance(session)
    if not summary.by_topic:
        return {}
    return {
        c.category.lower(): PERF_MIN + (PERF_MAX - PERF_MIN) * (c.score / 100.0)
        for c in summary.by_topic
    }


async def apply_opportunity(
    session: AsyncSession, events: list[Event], *, now
) -> None:
    """Compute + store opportunity_score and confidence_score for each event."""
    perf = await topic_performance_multipliers(session)
    matched = await _matched_topic_names(session, [e.id for e in events]) if perf else {}

    for event in events:
        row = (
            await session.execute(
                select(
                    func.avg(Source.confidence),
                    func.count(func.distinct(Source.id)),
                    func.avg(func.coalesce(func.length(ContentItem.text), 0)),
                )
                .select_from(ContentItem)
                .join(Source, ContentItem.source_id == Source.id)
                .where(ContentItem.event_id == event.id)
            )
        ).one()
        avg_conf = float(row[0]) if row[0] is not None else 0.6
        source_count = int(row[1] or 1)
        avg_item_len = float(row[2] or 0)

        acceleration = float((event.velocity or {}).get("acceleration", 0.0))
        age_hours = (now - event.first_seen_at).total_seconds() / 3600

        # Tilt personal relevance by how you actually perform on this event's topics.
        boost = 1.0
        if perf:
            factors = [perf[name] for name in matched.get(event.id, []) if name in perf]
            if factors:
                boost = max(factors)  # your best-performing matched topic leads

        result = compute_opportunity(
            OpportunityInputs(
                trend_score=event.trend_score,
                personal_relevance=min(100.0, event.personal_relevance * boost),
                age_hours=age_hours,
                acceleration=acceleration,
                source_confidence=avg_conf,
                source_count=source_count,
                content_gap=content_gap(source_count, avg_item_len),
            )
        )
        event.opportunity_score = result.opportunity_score
        event.confidence_score = round(100.0 * avg_conf, 2)
