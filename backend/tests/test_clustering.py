"""Tests for event clustering and text helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.pipeline.clustering import (
    ClusterItem,
    canonical_url,
    cluster_items,
    cosine,
)
from app.pipeline.text import jaccard, keywords

T0 = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)


def _item(id, emb, kw, url=None, minutes=0) -> ClusterItem:
    return ClusterItem(
        id=id,
        embedding=emb,
        keywords=set(kw),
        url=url,
        timestamp=T0 + timedelta(minutes=minutes),
    )


def test_keywords_and_jaccard() -> None:
    kw = keywords("OpenAI launches a new GPT model today")
    assert "openai" in kw and "gpt" in kw and "model" in kw
    assert "the" not in kw and "new" not in kw  # stopwords dropped
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), set()) == 0.0


def test_cosine_basics() -> None:
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine(None, [1, 0]) == 0.0


def test_same_event_clusters_together_across_sources() -> None:
    # An article, a tweet and a reddit post about the same OpenAI launch.
    a = _item("a", [0.90, 0.10, 0.0], {"openai", "gpt", "launch", "model"}, minutes=0)
    b = _item("b", [0.86, 0.14, 0.0], {"openai", "gpt", "drops", "model"}, minutes=15)
    c = _item("c", [0.88, 0.12, 0.0], {"openai", "gpt", "thoughts", "model"}, minutes=30)
    # An unrelated Docker story.
    d = _item("d", [0.02, 0.10, 0.95], {"docker", "compose", "release"}, minutes=20)

    clusters = cluster_items([a, b, c, d])
    sizes = sorted(len(cl.items) for cl in clusters)
    assert sizes == [1, 3]  # openai(3) + docker(1)

    big = max(clusters, key=lambda cl: len(cl.items))
    assert {it.id for it in big.items} == {"a", "b", "c"}


def test_shared_url_forces_same_event() -> None:
    # Different embeddings/keywords but identical canonical URL -> same event.
    a = _item("a", [1.0, 0.0, 0.0], {"alpha"}, url="https://ex.com/story?utm=1")
    b = _item("b", [0.0, 1.0, 0.0], {"omega"}, url="https://ex.com/story/")
    clusters = cluster_items([a, b])
    assert len(clusters) == 1
    assert canonical_url("https://ex.com/story?utm=1") == "ex.com/story"


def test_time_window_separates_old_item() -> None:
    a = _item("a", [0.9, 0.1, 0.0], {"openai", "gpt", "model"}, minutes=0)
    # Same topic but ~10 days later -> outside the 72h window -> separate event.
    b = ClusterItem(
        id="b",
        embedding=[0.9, 0.1, 0.0],
        keywords={"openai", "gpt", "model"},
        timestamp=T0 + timedelta(days=10),
    )
    clusters = cluster_items([a, b])
    assert len(clusters) == 2
