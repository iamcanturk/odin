"""Tests for the personal performance model."""

from __future__ import annotations

from app.models import Post, PostMetric, Topic
from app.pipeline.performance import compute_performance, content_type_tags, engagement


def test_content_type_tags() -> None:
    assert "question" in content_type_tags("Does this work?")
    assert "link" in content_type_tags("see http://x.com")
    assert "number" in content_type_tags("3 reasons")
    assert content_type_tags("a plain statement") == ["plain"]


def test_engagement_weighting() -> None:
    assert engagement(None) == 0.0
    high = engagement(PostMetric(likes=1, replies=1, reposts=1))
    assert high == 1.0 + 3.0 + 2.0


async def _post(session, text: str, likes: int) -> None:
    p = Post(platform="x", text=text, external_id=text[:20], status="posted", origin="imported")
    session.add(p)
    await session.flush()
    session.add(PostMetric(post_id=p.id, likes=likes))


async def test_performance_ranks_categories(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        session.add(Topic(name="AI", keywords=["openai", "gpt"]))
        # Questions perform well; plain statements poorly.
        await _post(session, "What will OpenAI ship next?", 100)
        await _post(session, "Another gpt question here?", 80)
        await _post(session, "a plain low-engagement note", 2)
        await session.commit()

        summary = await compute_performance(session)
        assert summary.total_posts == 3
        by_type = {c.category: c for c in summary.by_type}
        assert by_type["question"].score > by_type["plain"].score
        # AI topic matched the two OpenAI/gpt posts
        topics = {c.category: c for c in summary.by_topic}
        assert "AI" in topics and topics["AI"].posts == 2
        # best category normalized to 100
        assert max(c.score for c in summary.by_type) == 100.0
