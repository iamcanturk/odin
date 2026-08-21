"""Tests for corpus benchmarking and per-post post-mortems."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import ObservedTweet, Post, PostMetric, PostPrediction
from app.pipeline.benchmark import MIN_CORPUS, benchmark, percentile_of
from app.pipeline.postmortem import post_mortem

NOW = datetime.now(UTC)


async def _corpus(db_sessionmaker, likes: list[int], handle: str = "someone") -> None:
    async with db_sessionmaker() as session:
        for i, n in enumerate(likes):
            session.add(
                ObservedTweet(
                    external_id=f"t{i}",
                    author_handle=handle,
                    text=f"observed {i}",
                    likes=n,
                    impressions=n * 40,
                    observed_at=NOW - timedelta(hours=1),
                    posted_at=NOW - timedelta(hours=2),
                )
            )
        await session.commit()


async def _post(db_sessionmaker, text: str, likes: int, **kw) -> None:
    async with db_sessionmaker() as session:
        post = Post(
            platform="x", text=text, status="posted", origin="imported",
            posted_at=NOW - timedelta(hours=kw.pop("hours_ago", 24)),
        )
        session.add(post)
        await session.flush()
        session.add(PostMetric(post_id=post.id, likes=likes, captured_at=NOW, **kw))
        await session.commit()


def test_percentile_of_an_empty_corpus_is_zero():
    assert percentile_of([], 5.0) == 0.0


def test_percentile_places_a_value_in_the_distribution():
    corpus = [float(n) for n in range(100)]
    assert percentile_of(corpus, 50.0) == 50.0
    assert percentile_of(corpus, 0.0) == 0.0
    assert percentile_of(corpus, 200.0) == 100.0


async def test_a_thin_corpus_refuses_to_rank(db_sessionmaker):
    await _corpus(db_sessionmaker, [1, 2, 3])
    async with db_sessionmaker() as session:
        result = await benchmark(session)
    assert result.enough_data is False
    assert result.your_percentile is None


async def test_three_likes_against_a_low_corpus_is_good(db_sessionmaker):
    """The same 3 likes is a different verdict depending on the room."""
    await _corpus(db_sessionmaker, [0] * 60 + [1] * 20)
    await _post(db_sessionmaker, "my post", 3)
    async with db_sessionmaker() as session:
        result = await benchmark(session)
    assert result.enough_data is True
    assert result.posts[0].verdict == "top"


async def test_three_likes_against_a_strong_corpus_is_weak(db_sessionmaker):
    await _corpus(db_sessionmaker, list(range(100, 100 + MIN_CORPUS + 10)))
    await _post(db_sessionmaker, "my post", 3)
    async with db_sessionmaker() as session:
        result = await benchmark(session)
    assert result.posts[0].verdict == "below"
    assert result.posts[0].like_percentile == 0.0


async def test_own_tweets_are_excluded_from_the_yardstick(db_sessionmaker):
    """Benchmarking yourself against yourself measures nothing."""
    await _corpus(db_sessionmaker, [500] * (MIN_CORPUS + 5), handle="me")
    async with db_sessionmaker() as session:
        result = await benchmark(session, own_handles={"me"})
    assert result.enough_data is False


async def test_post_mortem_without_metrics_says_so(db_sessionmaker):
    async with db_sessionmaker() as session:
        post = Post(platform="x", text="silent", status="posted", origin="generated")
        session.add(post)
        await session.flush()
        m = await post_mortem(session, post)
    assert m.likes == 0
    assert any("metrik yok" in lesson for lesson in m.lessons)


async def test_post_mortem_calls_out_an_over_optimistic_prediction(db_sessionmaker):
    async with db_sessionmaker() as session:
        post = Post(
            platform="x", text="a claim about pgvector", status="posted",
            origin="generated", posted_at=NOW - timedelta(hours=48),
        )
        session.add(post)
        await session.flush()
        session.add(PostMetric(post_id=post.id, likes=2, replies=0, reposts=0, captured_at=NOW))
        session.add(
            PostPrediction(
                post_id=post.id, predicted_at=NOW - timedelta(hours=48),
                model_version="test", viral_score=70.0, x_simulation=60.0,
                opportunity_score=50.0, predicted_likes=40,
            )
        )
        await session.flush()
        m = await post_mortem(session, post)

    assert m.settled is True
    pred = next(c for c in m.comparisons if c.label == "prediction")
    assert pred.verdict == "worse"
    assert any("iyimser" in lesson for lesson in m.lessons)


async def test_post_mortem_is_provisional_before_the_numbers_settle(db_sessionmaker):
    async with db_sessionmaker() as session:
        post = Post(
            platform="x", text="fresh", status="posted", origin="generated",
            posted_at=NOW - timedelta(minutes=30),
        )
        session.add(post)
        await session.flush()
        session.add(PostMetric(post_id=post.id, likes=1, captured_at=NOW))
        await session.flush()
        m = await post_mortem(session, post)
    assert m.settled is False
    assert any("erken" in lesson for lesson in m.lessons)
