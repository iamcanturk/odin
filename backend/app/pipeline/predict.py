"""Predict engagement for an approved candidate (PROJECT.md §34).

A transparent v1 heuristic: anchor on the user's recent median likes (or a small
default when there's no history) and scale by the candidate's viral score and the
X-simulation reply/repost probabilities. Predictions are stored immutably so the
feedback loop can later compare them to actual metrics.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.pipeline.xsim import simulate

MODEL_VERSION = "predict-v1"
DEFAULT_BASELINE_LIKES = 8  # cold-start anchor when the user has no post history


@dataclass
class Prediction:
    viral_score: float
    x_simulation: float
    opportunity_score: float
    predicted_likes: int
    predicted_impressions: int
    predicted_replies: int
    predicted_reposts: int
    model_version: str = MODEL_VERSION
    scoring_version: str | None = None
    algorithm_version: str | None = None
    features: dict[str, float] = field(default_factory=dict)


def baseline_likes(recent_likes: list[int]) -> float:
    vals = [v for v in recent_likes if v is not None]
    return float(statistics.median(vals)) if vals else float(DEFAULT_BASELINE_LIKES)


def predict(
    text: str,
    *,
    viral_score: float,
    opportunity_score: float,
    recent_likes: list[int],
    trend_fit: float = 0.0,
    personal_fit: float = 0.0,
) -> Prediction:
    xr = simulate(text, trend_fit=trend_fit, personal_fit=personal_fit)
    base = baseline_likes(recent_likes)

    # Viral score 50 ≈ on par with the user's median; higher scales up, lower scales down.
    multiplier = max(0.2, viral_score / 50.0)
    likes = round(base * multiplier)
    impressions = round(likes * 45)  # rough public engagement-rate assumption (~2%)
    replies = round(likes * xr.probabilities["reply"] / max(xr.probabilities["like"], 1e-6) * 0.5)
    reposts = round(likes * xr.probabilities["repost"] / max(xr.probabilities["like"], 1e-6) * 0.5)

    return Prediction(
        viral_score=round(viral_score, 2),
        x_simulation=xr.sim_score,
        opportunity_score=round(opportunity_score, 2),
        predicted_likes=likes,
        predicted_impressions=impressions,
        predicted_replies=max(0, replies),
        predicted_reposts=max(0, reposts),
        scoring_version=xr.scoring_version,
        algorithm_version=xr.algorithm_version,
        features={
            "baseline_likes": base,
            "multiplier": round(multiplier, 3),
            **{f"p_{k}": v for k, v in xr.probabilities.items()},
        },
    )
