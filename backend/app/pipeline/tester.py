"""Tweet tester (PROJECT.md §19): analyze pasted text into a scored breakdown + why.

Combines the X algorithm SIMULATION (estimate), personal style fit, trend fit and
novelty. All ranking language is an estimate, never a guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, StyleProfile
from app.models.enums import EventStatus
from app.pipeline.clustering import cosine
from app.pipeline.xsim import extract_features, simulate
from app.providers.base import EmbeddingProvider

SCORING_VERSION = "tester-v1"
DISCLAIMER = "X Algorithm Simulation — a public estimate, not a guaranteed score."


@dataclass
class TesterResult:
    viral_potential: float = 0.0
    x_simulation: float = 0.0
    personal_fit: float = 0.0
    trend_fit: float = 0.0
    novelty: float = 0.0
    reply_potential: float = 0.0
    bookmark_potential: float = 0.0
    negative_risk: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    scoring_version: str = SCORING_VERSION
    disclaimer: str = DISCLAIMER


def combine_viral(xsim: float, personal: float, trend: float, novelty: float) -> float:
    return round(0.40 * xsim + 0.30 * personal + 0.20 * trend + 0.10 * novelty, 2)


async def analyze(session: AsyncSession, text: str, embedder: EmbeddingProvider) -> TesterResult:
    vec = await embedder.embed_text(text)

    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    personal_fit = (
        round(100.0 * cosine(vec, list(profile.centroid)), 2)
        if profile is not None and profile.centroid is not None
        else 50.0
    )

    events = list(
        (
            await session.execute(
                select(Event)
                .where(Event.status != EventStatus.ARCHIVED)
                .order_by(Event.trend_score.desc())
                .limit(20)
            )
        ).scalars()
    )
    sims = [cosine(vec, list(e.centroid)) for e in events if e.centroid is not None]
    trend_sim = max(sims) if sims else 0.0
    trend_fit = round(100.0 * trend_sim, 2)
    novelty = round(100.0 * (1.0 - trend_sim), 2)

    xr = simulate(text, trend_fit=trend_sim, personal_fit=personal_fit / 100.0)
    viral = combine_viral(xr.sim_score, personal_fit, trend_fit, novelty)

    f = extract_features(text)
    strengths: list[str] = []
    weaknesses: list[str] = []
    if xr.sim_score >= 50:
        strengths.append("Strong predicted ranking signals.")
    if personal_fit >= 60:
        strengths.append("Matches your historical voice.")
    if trend_fit >= 60:
        strengths.append("Highly relevant to a currently trending event.")
    if f.has_question:
        strengths.append("Invites replies, which the ranker weights heavily.")
    if novelty < 35:
        weaknesses.append("Low novelty — similar framing is already widespread.")
    if xr.probabilities["negative"] >= 0.05:
        weaknesses.append("Elevated negative-feedback risk.")
    if f.has_link:
        weaknesses.append("External link may reduce reach.")
    if not strengths:
        strengths.append("No standout strengths detected.")
    if not weaknesses:
        weaknesses.append("No major weaknesses detected.")

    return TesterResult(
        viral_potential=viral,
        x_simulation=xr.sim_score,
        personal_fit=personal_fit,
        trend_fit=trend_fit,
        novelty=novelty,
        reply_potential=round(100.0 * xr.probabilities["reply"], 2),
        bookmark_potential=round(100.0 * xr.probabilities["bookmark"], 2),
        negative_risk=round(100.0 * xr.probabilities["negative"], 2),
        probabilities=xr.probabilities,
        strengths=strengths,
        weaknesses=weaknesses,
    )
