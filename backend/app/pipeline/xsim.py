"""X Algorithm SIMULATION — a public-concept ESTIMATE, never a guaranteed score.

Models the scoring approach disclosed in xai-org/x-algorithm (the open-source "For You"
ranker): predict per-action engagement probabilities, combine with the published linear
weight vector, then map to 0-100. Deterministic + explainable. This is NOT X's production
model — UI-facing language must say "estimate". (PROJECT.md §16-18.)

Weights below are the Aug-2026 disclosed values from
https://github.com/xai-org/x-algorithm/blob/main/home-mixer/params/param.rs
(cross-checked against the explainx.ai weights table). X retrains ~monthly, so treat the
exact numbers as a snapshot, not a constant.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

ALGORITHM_VERSION = "xai-x-algorithm-2026-08"
SCORING_VERSION = "xsim-v2"

# Published relative weights applied to PREDICTED action probabilities. Positive actions
# scale reach up; negative actions (report/mute/not-interested/block) scale it sharply down.
WEIGHTS = {
    # positive
    "copy_link_share": 20.0,  # the single strongest positive signal
    "reply": 5.0,
    "quote": 5.0,
    "dm_share": 5.0,
    "follow": 4.0,
    "share": 2.0,
    "repost": 1.0,
    "like": 0.5,  # baseline unit
    "post_click": 0.4,
    "link_open": 0.2,
    "bookmark": 0.0,  # tracked but currently unweighted
    "profile_click": 0.0,  # now ignored by the ranker
    # negative (probabilities are tiny, but the weights are large — abuse is punished hard)
    "mute": -58.8,
    "not_interested": -43.2,
    "block": -31.2,
    "report": -234.0,
}

NEGATIVE_ACTIONS = ("mute", "not_interested", "block", "report")

# Post-scoring multipliers X applies with network context we don't have for a single tweet.
# Surfaced as explanatory notes; the out-of-network discount can be applied if known.
OON_WEIGHT_FACTOR = 0.75
MUTUAL_FOLLOW_REPLY_BOOST = 15.0  # reply 5.0 -> 20.0 when replier follows the author

# Map the weighted sum to 0-100 with a sigmoid so scores spread usefully. Re-tuned for the
# v2 weight vector (positive mass ~1.0, negative tail dominated by the tiny report prob).
_SIG_MID = 0.35
_SIG_STEEP = 3.4


def _to_score(raw: float) -> float:
    return round(100.0 / (1.0 + math.exp(-_SIG_STEEP * (raw - _SIG_MID))), 2)


_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_CONTRARIAN = ("wrong", "unpopular", "hot take", "nobody", "stop", "myth", "actually", "overrated")
# Signals that a post is worth saving / sharing on (drives copy-link share + bookmark).
_SHAREABLE = (
    "how", "guide", "tips", "thread", "tutorial", "resource", "free", "cheatsheet",
    "steps", "list", "learn", "release", "launch", "open source", "vs",
)


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
    shareable: float = 0.0  # 0-1: how "save/share-worthy" the post reads


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
    has_link = "http" in low
    has_number = any(w.isdigit() for w in words)
    shareable = min(
        1.0,
        0.3 * has_link
        + 0.25 * has_number
        + 0.3 * sum(1 for w in _SHAREABLE if w in low),
    )
    return Features(
        length=len(text),
        word_count=len(words),
        has_question="?" in text,
        has_link=has_link,
        has_number=has_number,
        hook=bool(words) and words[0].lower() in ("how", "why", "what", "stop", "the"),
        exclaim="!" in text,
        controversy=controversy,
        shareable=shareable,
    )


def action_probabilities(f: Features, *, trend_fit: float, personal_fit: float) -> dict[str, float]:
    tf, pf = _clamp(trend_fit), _clamp(personal_fit)
    sh = f.shareable
    return {
        # positive
        "copy_link_share": _clamp(0.004 + 0.03 * sh + 0.01 * f.has_number),
        "reply": _clamp(0.015 + 0.06 * f.has_question + 0.05 * f.controversy),
        "quote": _clamp(0.006 + 0.03 * f.controversy + 0.015 * f.hook),
        "dm_share": _clamp(0.004 + 0.02 * sh),
        "follow": _clamp(0.002 + 0.012 * pf + 0.006 * f.hook),
        "share": _clamp(0.006 + 0.02 * sh + 0.01 * f.has_number),
        "repost": _clamp(0.01 + 0.02 * f.hook + 0.02 * tf + 0.02 * f.has_number),
        "like": _clamp(0.08 + 0.04 * f.hook + 0.03 * tf + 0.03 * pf),
        "post_click": _clamp(0.02 + 0.02 * f.hook + 0.02 * f.has_link),
        "link_open": _clamp(0.01 + 0.05 * f.has_link),
        "bookmark": _clamp(0.02 + 0.03 * f.has_number + 0.03 * sh),
        "profile_click": _clamp(0.01 + 0.02 * pf),
        # Negative — kept genuinely tiny so the large weights don't collapse every score.
        # Report/block track true abuse, which we can't infer from spicy wording; hold them
        # near baseline. Contrarian framing mostly raises mutes / "not interested", not reports.
        "report": _clamp(0.0008),
        "block": _clamp(0.0008),
        "mute": _clamp(0.0015 + 0.003 * f.controversy),
        "not_interested": _clamp(0.002 + 0.004 * f.controversy + 0.004 * f.has_link),
    }


def negative_probability(probs: dict[str, float]) -> float:
    """Aggregate negative-feedback probability (for a single 'risk' readout)."""
    return _clamp(sum(probs[k] for k in NEGATIVE_ACTIONS))


def simulate(text: str, *, trend_fit: float = 0.0, personal_fit: float = 0.0) -> XSimResult:
    f = extract_features(text)
    probs = action_probabilities(f, trend_fit=trend_fit, personal_fit=personal_fit)
    raw = sum(WEIGHTS[k] * probs[k] for k in WEIGHTS)
    sim = _to_score(raw)

    notes: list[str] = []
    if f.shareable >= 0.3:
        notes.append("Save/share-worthy framing — copy-link shares are the top-weighted signal.")
    if f.has_question:
        notes.append("Questions raise reply probability, which the ranker weights ~10x a like.")
    if f.controversy > 0:
        notes.append("Contrarian framing boosts replies/quotes but also the heavy report penalty.")
    if f.has_link:
        notes.append("Links are no longer penalised in the weight vector (a small link-open plus).")
    notes.append("Out-of-network reach is discounted ~0.75x; posts stay eligible ~48h (no decay).")
    if not notes:
        notes.append("Neutral post — no strong ranking signals detected.")

    return XSimResult(
        probabilities={k: round(v, 4) for k, v in probs.items()},
        raw_score=round(raw, 4),
        sim_score=sim,
        notes=notes,
    )
