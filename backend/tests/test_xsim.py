"""Tests for the X algorithm simulation (xai-org/x-algorithm public estimate)."""

from __future__ import annotations

from app.pipeline.xsim import (
    NEGATIVE_ACTIONS,
    SCORING_VERSION,
    WEIGHTS,
    action_probabilities,
    extract_features,
    negative_probability,
    simulate,
)


def test_probabilities_bounded() -> None:
    f = extract_features("Why is nobody talking about this? http://x.com stop the myths!")
    probs = action_probabilities(f, trend_fit=1.0, personal_fit=1.0)
    assert all(0.0 <= p <= 1.0 for p in probs.values())
    # every weighted action has a predicted probability
    assert set(probs) == set(WEIGHTS)


def test_deterministic_and_versioned() -> None:
    a = simulate("OpenAI ships GPT-X", trend_fit=0.5)
    b = simulate("OpenAI ships GPT-X", trend_fit=0.5)
    assert a.sim_score == b.sim_score
    assert a.scoring_version == SCORING_VERSION


def test_copy_link_share_is_top_weight() -> None:
    # The single strongest positive signal in the disclosed weight vector.
    positives = {k: v for k, v in WEIGHTS.items() if v > 0}
    assert max(positives, key=positives.get) == "copy_link_share"
    assert WEIGHTS["copy_link_share"] == 20.0
    # negatives are decomposed; report dominates the tail
    assert min(WEIGHTS, key=WEIGHTS.get) == "report"


def test_question_raises_reply_probability() -> None:
    plain = simulate("OpenAI shipped a new model today.")
    question = simulate("Did OpenAI just make agents obsolete?")
    assert question.probabilities["reply"] > plain.probabilities["reply"]


def test_shareable_post_scores_higher_than_bland() -> None:
    bland = simulate("posted something")
    resource = simulate(
        "How to self-host Postgres with pgvector: a step-by-step guide with 7 tips. "
        "Free and open source."
    )
    assert resource.probabilities["copy_link_share"] > bland.probabilities["copy_link_share"]
    assert resource.sim_score > bland.sim_score


def test_links_not_penalised() -> None:
    no_link = simulate("A clean technical take on retrieval quality")
    with_link = simulate("A clean technical take on retrieval quality http://ex.com")
    # Links no longer cut score via a report penalty; they add a small link-open signal.
    assert with_link.probabilities["link_open"] > no_link.probabilities["link_open"]
    assert with_link.probabilities["report"] == no_link.probabilities["report"]
    assert any("link" in n.lower() for n in with_link.notes)


def test_negative_probability_aggregates() -> None:
    r = simulate("Hot take: RAG is overrated. Nobody wants to admit it.", personal_fit=0.8)
    agg = negative_probability(r.probabilities)
    assert agg == min(1.0, sum(r.probabilities[k] for k in NEGATIVE_ACTIONS))
    assert 0.0 <= agg <= 1.0


def test_score_in_range() -> None:
    for text in ["ok", "Hot take: RAG is overrated.", "How to ship faster: 5 tips (free guide)"]:
        r = simulate(text, personal_fit=0.8)
        assert 0.0 <= r.sim_score <= 100.0
