"""Tests for the repetition guard: have you already said this?"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Post
from app.models.base import EMBED_DIM
from app.pipeline.repetition import check_repetition
from app.providers.embedding import HashEmbeddingProvider


async def _seed(db_sessionmaker, texts: list[tuple[str, int]]) -> None:
    """texts = [(body, days_ago)]"""
    now = datetime.now(UTC)
    async with db_sessionmaker() as session:
        for body, days_ago in texts:
            session.add(
                Post(
                    platform="x",
                    text=body,
                    status="posted",
                    origin="imported",
                    posted_at=now - timedelta(days=days_ago),
                )
            )
        await session.commit()


async def test_no_history_means_nothing_to_repeat(db_sessionmaker):
    async with db_sessionmaker() as session:
        result = await check_repetition(session, "brand new take", HashEmbeddingProvider(EMBED_DIM))
    assert result.is_repeat is False
    assert result.matches == []


async def test_identical_text_is_flagged(db_sessionmaker):
    await _seed(db_sessionmaker, [("pgvector beats a bolt-on vector DB for small corpora", 10)])
    async with db_sessionmaker() as session:
        result = await check_repetition(
            session,
            "pgvector beats a bolt-on vector DB for small corpora",
            HashEmbeddingProvider(EMBED_DIM),
        )
    assert result.is_repeat is True
    assert result.matches[0].days_ago == 10
    assert result.matches[0].similarity >= result.threshold


async def test_unrelated_text_is_not_a_repeat(db_sessionmaker):
    await _seed(db_sessionmaker, [("pgvector beats a bolt-on vector DB", 5)])
    async with db_sessionmaker() as session:
        result = await check_repetition(
            session, "the CVSS score alone tells you nothing", HashEmbeddingProvider(EMBED_DIM)
        )
    assert result.is_repeat is False


async def test_old_enough_to_say_again(db_sessionmaker):
    """Repeating yourself after a year is a callback, not a repeat."""
    await _seed(db_sessionmaker, [("pgvector beats a bolt-on vector DB", 400)])
    async with db_sessionmaker() as session:
        result = await check_repetition(
            session, "pgvector beats a bolt-on vector DB", HashEmbeddingProvider(EMBED_DIM)
        )
    assert result.is_repeat is False


async def test_embeddings_are_cached_on_first_check(db_sessionmaker):
    """Posts predating the embedding column get backfilled in place, not re-embedded."""
    await _seed(db_sessionmaker, [("a post written before the column existed", 3)])
    async with db_sessionmaker() as session:
        await check_repetition(session, "anything", HashEmbeddingProvider(EMBED_DIM))
        await session.commit()
    async with db_sessionmaker() as session:
        post = (await session.execute(__import__("sqlalchemy").select(Post))).scalar_one()
        assert post.embedding is not None
