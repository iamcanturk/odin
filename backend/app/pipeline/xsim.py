"""X Algorithm SIMULATION — a public-concept ESTIMATE, never a guaranteed score.

Models the publicly discussed heavy-ranker approach: predict engagement-action
probabilities, then combine with the public weighting. Deterministic + explainable.
This is NOT X's production model — UI-facing language must say "estimate".
(PROJECT.md §16-18.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ALGORITHM_VERSION = "public-heavy-ranker-approx"
SCORING_VERSION = "xsim-v1"

# Publicly discussed relative weights of predicted actions (approximate, illustrative).
WEIGHTS = {
    "like": 0.5,
    "reply": 13.5,
    "repost": 1.0,
    "profile_click": 12.0,
    "good_click": 11.0,
    "bookmark": 0.5,
    "follow": 24.0,
    "negative": -74.0,
}

# Rough max of the positive weighted sum, used to normalize to 0-100.
_NORM_MAX = 6.0

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_CONTRARIAN = ("wrong", "unpopular", "hot take", "nobody", "stop", "myth", "actually", "overrated")


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Features:
    length: int = 0
    word_count: int = 0
    has_question: bool = False
    has_link: bool = False
    has_number: bool = False
    hook: bool = False
    exclaim: bool = False
    controversy: float = 0.0


@dataclass
class XSimResult:
    probabilities: dict[str, float] = field(default_factory=dict)
    raw_score: float = 0.0
    sim_score: float = 0.0  # 0-100, labeled ESTIMATE
    algorithm_version: str = ALGORITHM_VERSION
    scoring_version: str = SCORING_VERSION
    notes: list[str] = field(default_factory=list)


def extract_features(text: str) -> Features:
    words = _WORD_RE.findall(text)
    low = text.lower()
    controversy = min(1.0, sum(low.count(w) for w in _CONTRARIAN) * 0.34)
    return Features(
        length=len(text),
        word_count=len(words),
        has_question="?" in text,
        has_link="http" in low,
        has_number=any(w.isdigit() for w in words),
        hook=bool(words) and words[0].lower() in ("how", "why", "what", "stop", "the"),
        exclaim="!" in text,
        controversy=controversy,
    )


def action_probabilities(f: Features, *, trend_fit: float, personal_fit: float) -> dict[str, float]:
    tf, pf = _clamp(trend_fit), _clamp(personal_fit)
    return {
        "like": _clamp(0.06 + 0.04 * f.hook + 0.03 * tf + 0.03 * pf - 0.02 * f.has_link),
        "reply": _clamp(0.01 + 0.06 * f.has_question + 0.05 * f.controversy),
        "repost": _clamp(0.01 + 0.02 * f.hook + 0.02 * tf + 0.02 * f.has_number),
        "profile_click": _clamp(0.01 + 0.02 * pf + 0.02 * f.hook),
        "good_click": _clamp(0.02 + 0.02 * f.has_link + 0.02 * tf),
        "bookmark": _clamp(0.02 + 0.03 * f.has_number + 0.02 * tf),
        "follow": _clamp(0.002 + 0.012 * pf),
        "negative": _clamp(0.005 + 0.035 * f.controversy + 0.02 * f.has_link),
    }


def simulate(text: str, *, trend_fit: float = 0.0, personal_fit: float = 0.0) -> XSimResult:
    f = extract_features(text)
    probs = action_probabilities(f, trend_fit=trend_fit, personal_fit=personal_fit)
    raw = sum(WEIGHTS[k] * probs[k] for k in WEIGHTS)
    sim = round(100.0 * _clamp(raw / _NORM_MAX), 2)

    notes: list[str] = []
    if f.has_question:
        notes.append("Questions raise reply probability, which the ranker weights heavily.")
    if f.has_link:
        notes.append("External links tend to reduce reach and raise negative-signal risk.")
    if f.controversy > 0:
        notes.append("Contrarian framing boosts replies but also negative feedback.")
    if not notes:
        notes.append("Neutral post — no strong ranking signals detected.")

    return XSimResult(
        probabilities={k: round(v, 4) for k, v in probs.items()},
        raw_score=round(raw, 4),
        sim_score=sim,
        notes=notes,
    )
