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


def test_turkish_words_are_not_truncated_into_fragments() -> None:
    """The old ASCII-only tokenizer turned 'yazdım' into 'yazd' and 'hesabı' into 'hesab'."""
    from app.pipeline.text import keywords

    terms = keywords("Docker imajlarını küçülttüm ve hesabımı güncelledim")
    assert "imajlarını" in terms
    assert "hesabımı" in terms
    assert not any(t in terms for t in ("yazd", "hesab", "imajlar"))


def test_turkish_filler_words_are_not_style_signal() -> None:
    from app.pipeline.text import keywords

    terms = keywords("Abi ama ben sonra çok yani işte falan bir şey yapacağım")
    for filler in ("abi", "ama", "ben", "sonra", "yani", "işte", "falan"):
        assert filler not in terms


def test_top_terms_need_to_appear_across_posts() -> None:
    """One rambling post must not inject its whole vocabulary into 'how you write'.

    The cross-post floor only kicks in once there's a real corpus (MIN_CORPUS_FOR_FLOOR),
    so this uses enough posts to trigger it.
    """
    posts = [
        "Docker imajlarını küçültmek için multi-stage build",
        "Docker katman sırası cache için önemli",
        "GitHub Actions ile Docker build hızlandırma",
        "Docker build süresini yarıya indirdim",
        "Docker compose ile local ortam kurulumu",
        "Build cache invalidation en sinir bozucu konu",
        "GitHub Actions cache ayarları",
        "Bugün kahve içtim ve parkta yürüdüm, hava enfesti",
    ]
    fp = compute_style_profile(posts)
    assert "docker" in fp.top_terms
    # Words unique to the one off-topic post are excluded.
    for once in ("kahve", "parkta", "yürüdüm", "enfesti"):
        assert once not in fp.top_terms


def test_words_in_most_posts_are_background_not_voice() -> None:
    """No stopword list is ever complete.

    'gerekiyor', 'şekilde', 'gerçekten' aren't stopwords but say nothing about what
    someone writes about. A term appearing in most posts is background language, so it's
    excluded by document frequency rather than by chasing an endless word list.
    """
    filler = "Bu gerçekten yeni bir şekilde gerekiyor artık"
    topics = ["docker", "docker", "kubernetes", "kubernetes", "postgres", "postgres",
              "redis", "redis", "nginx", "nginx"]
    fp = compute_style_profile([f"{filler} {t}" for t in topics])

    assert set(fp.top_terms) == {"docker", "kubernetes", "postgres", "redis", "nginx"}
    for background in ("gerçekten", "şekilde", "gerekiyor", "artık", "yeni"):
        assert background not in fp.top_terms
