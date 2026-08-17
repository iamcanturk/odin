"""Tests for style fingerprint computation (pure)."""

from __future__ import annotations

from app.pipeline.style import compute_style_profile

POSTS = [
    "Why do most AI agent demos ignore infra cost? The real bottleneck isn't intelligence.",
    "How to actually ship an LLM feature: start with evals, not the model.",
    "Hot take: RAG is overused. Most teams need better retrieval, not more context.",
    "Docker tip: multi-stage builds cut your image size dramatically. Try it today!",
]


def test_empty_profile() -> None:
    fp = compute_style_profile([])
    assert fp.post_count == 0
    assert "empty" in fp.summary.lower()


def test_features_computed() -> None:
    fp = compute_style_profile(POSTS)
    assert fp.post_count == 4
    f = fp.features
    assert f["avg_length"] > 0
    # 1 of the 4 sample posts asks a question.
    assert f["question_rate"] == 0.25
    assert "avg_sentence_length" in f and f["avg_sentence_length"] > 0
    assert isinstance(fp.top_terms, list) and len(fp.top_terms) > 0


def test_hook_and_question_detection() -> None:
    fp = compute_style_profile(["Why does this matter?", "How to win.", "A plain statement."])
    # first two start with hook words
    assert fp.features["hook_rate"] >= 2 / 3


def test_summary_is_descriptive() -> None:
    fp = compute_style_profile(POSTS)
    assert "chars/post" in fp.summary
    assert "Frequent terms" in fp.summary
