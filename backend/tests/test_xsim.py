"""Tests for the X algorithm simulation (public estimate)."""

from __future__ import annotations

from app.pipeline.xsim import (
    SCORING_VERSION,
    action_probabilities,
    extract_features,
    simulate,
)


def test_probabilities_bounded() -> None:
    f = extract_features("Why is nobody talking about this? http://x.com stop the myths!")
    probs = action_probabilities(f, trend_fit=1.0, personal_fit=1.0)
    assert all(0.0 <= p <= 1.0 for p in probs.values())


def test_deterministic_and_versioned() -> None:
    a = simulate("OpenAI ships GPT-X", trend_fit=0.5)
    b = simulate("OpenAI ships GPT-X", trend_fit=0.5)
    assert a.sim_score == b.sim_score
    assert a.scoring_version == SCORING_VERSION


def test_question_raises_reply_probability() -> None:
    plain = simulate("OpenAI shipped a new model today.")
    question = simulate("Did OpenAI just make agents obsolete?")
    assert question.probabilities["reply"] > plain.probabilities["reply"]


def test_link_raises_negative_and_notes() -> None:
    no_link = simulate("A clean technical take on retrieval quality")
    with_link = simulate("A clean technical take on retrieval quality http://ex.com")
    assert with_link.probabilities["negative"] > no_link.probabilities["negative"]
    assert any("link" in n.lower() for n in with_link.notes)


def test_score_in_range() -> None:
    r = simulate("Hot take: RAG is overrated. Nobody wants to admit it.", personal_fit=0.8)
    assert 0.0 <= r.sim_score <= 100.0
