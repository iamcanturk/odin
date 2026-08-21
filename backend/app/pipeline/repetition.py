"""Have you already said this? (repetition guard)

A generator that doesn't know your history will eventually reproduce a point you've
already made. That's the specific failure mode of AI-assisted posting: each draft looks
fine in isolation, and only the timeline shows you repeating yourself.

Uses the post embeddings that already exist for the style profile, so this costs one
embedding call per check and no LLM at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post
from app.pipeline.clustering import cosine
from app.providers.base import EmbeddingProvider

# Cosine similarity above which two posts are "the same point". e5 rates loosely related
# tech posts around 0.75-0.82, so the bar sits above that to avoid crying wolf.
SIMILAR = 0.88
# Saying the same thing a year apart is fine; a month apart is a repeat.
LOOKBACK_DAYS = 120


@dataclass
class SimilarPost:
    post_id: str
    text: str
    similarity: float
    posted_at: datetime | None
    days_ago: int | None


@dataclass
class RepetitionCheck:
    is_repeat: bool
    threshold: float
    matches: list[SimilarPost]


async def check_repetition(
    session: AsyncSession,
    text: str,
    embedder: EmbeddingProvider,
    *,
    threshold: float = SIMILAR,
    lookback_days: int = LOOKBACK_DAYS,
    limit: int = 3,
    now: datetime | None = None,
) -> RepetitionCheck:
    """Compare a draft against what you've actually published."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)

    posts = list(
        (
            await session.execute(select(Post).where(Post.status == "posted"))
        ).scalars()
    )
    posts = [p for p in posts if _in_window(p, cutoff)]
    if not posts:
        return RepetitionCheck(is_repeat=False, threshold=threshold, matches=[])

    await _fill_embeddings(session, posts, embedder)
    vector = await embedder.embed_text(text)
    scored: list[SimilarPost] = []
    for post in posts:
        if post.embedding is None:
            continue
        posted = _aware(post.posted_at)
        similarity = cosine(vector, list(post.embedding))
        if similarity < threshold:
            continue
        scored.append(
            SimilarPost(
                post_id=str(post.id),
                text=post.text[:200],
                similarity=round(similarity, 3),
                posted_at=posted,
                days_ago=int((now - posted).days) if posted else None,
            )
        )

    scored.sort(key=lambda s: s.similarity, reverse=True)
    return RepetitionCheck(
        is_repeat=bool(scored), threshold=threshold, matches=scored[:limit]
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _in_window(post: Post, cutoff: datetime) -> bool:
    posted = _aware(post.posted_at)
    return posted is None or posted >= cutoff


async def _fill_embeddings(
    session: AsyncSession, posts: list[Post], embedder: EmbeddingProvider
) -> None:
    """Embed any post that predates the embedding column, once."""
    missing = [p for p in posts if p.embedding is None]
    if not missing:
        return
    vectors = await embedder.embed_texts([p.text for p in missing])
    for post, vector in zip(missing, vectors, strict=True):
        post.embedding = vector
    await session.flush()
