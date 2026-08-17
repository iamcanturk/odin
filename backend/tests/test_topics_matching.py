"""Tests for topic matching (pure scoring)."""

from __future__ import annotations

from app.pipeline.topics import TopicView, best_relevance, score_topic

AI = TopicView(
    id="ai",
    keywords={"openai", "gpt", "llm", "agents"},
    exclude={"crypto", "nft"},
    embedding=[1.0, 0.0, 0.0],
)


def test_include_keyword_hit_boosts_relevance() -> None:
    score = score_topic({"openai", "model", "launch"}, [0.9, 0.1, 0.0], AI)
    assert score > 0.5


def test_exclude_keyword_suppresses() -> None:
    # Relevant embedding + keyword, but an excluded term forces 0.
    score = score_topic({"openai", "crypto"}, [1.0, 0.0, 0.0], AI)
    assert score == 0.0


def test_unrelated_event_low_relevance() -> None:
    score = score_topic({"gardening", "tomatoes"}, [0.0, 0.0, 1.0], AI)
    assert score < 0.2


def test_best_relevance_is_max_scaled() -> None:
    assert best_relevance([("a", 0.3), ("b", 0.82)]) == 82.0
    assert best_relevance([]) == 0.0


def test_embedding_only_still_contributes() -> None:
    # No keyword overlap, but a near-parallel embedding still yields some relevance.
    score = score_topic({"unrelated"}, [0.98, 0.02, 0.0], AI)
    assert 0.0 < score < 0.7
