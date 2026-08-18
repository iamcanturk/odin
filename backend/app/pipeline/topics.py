"""Topic matching: score events against user topics and derive personal relevance.

Combines embedding similarity with include/exclude keyword rules (PROJECT.md §28).
Exclude keywords hard-suppress a match; include-keyword overlap boosts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventTopic, Topic
from app.pipeline.clustering import cosine
from app.pipeline.text import jaccard
from app.providers.base import EmbeddingProvider

W_EMBED = 0.6
W_KEYWORD = 0.4


@dataclass
class TopicView:
    id: object
    keywords: set[str] = field(default_factory=set)
    exclude: set[str] = field(default_factory=set)
    embedding: list[float] | None = None
    priority_weight: float = 1.0


def score_topic(
    event_keywords: set[str], event_embedding: list[float] | None, topic: TopicView
) -> float:
    """Relevance of an event to a topic in [0, 1]. Exclude keywords force 0."""
    if topic.exclude & event_keywords:
        return 0.0
    emb = cosine(event_embedding, topic.embedding)
    kw = jaccard(event_keywords, topic.keywords)
    # Direct include-keyword hit is a strong signal even without embeddings.
    if topic.keywords & event_keywords:
        kw = max(kw, 0.5)
    return W_EMBED * emb + W_KEYWORD * kw


def best_relevance(matches: list[tuple[object, float]]) -> float:
    """Personal relevance (0-100) = best topic match."""
    if not matches:
        return 0.0
    return round(100.0 * max(score for _, score in matches), 2)


def _topic_text(topic: Topic) -> str:
    return " ".join([topic.name, *(topic.keywords or [])]).strip()


async def ensure_topic_embeddings(
    session: AsyncSession, topics: list[Topic], embedder: EmbeddingProvider
) -> None:
    """Compute + persist embeddings for topics that don't have one yet."""
    missing = [t for t in topics if t.embedding is None and _topic_text(t)]
    if not missing:
        return
    vectors = await embedder.embed_texts([_topic_text(t) for t in missing])
    for topic, vector in zip(missing, vectors, strict=False):
        topic.embedding = vector


async def apply_topic_matching(
    session: AsyncSession,
    events: list[Event],
    embedder: EmbeddingProvider,
    *,
    min_relevance: float = 0.05,
    top_k: int = 3,
) -> None:
    """Match each event against enabled topics; upsert event_topics + personal_relevance."""
    if not events:
        return
    topics = list(
        (await session.execute(select(Topic).where(Topic.enabled.is_(True)))).scalars()
    )
    if not topics:
        return
    await ensure_topic_embeddings(session, topics, embedder)

    views = [
        TopicView(
            id=t.id,
            keywords={k.lower() for k in (t.keywords or [])},
            exclude={k.lower() for k in (t.exclude_keywords or [])},
            embedding=list(t.embedding) if t.embedding is not None else None,
        )
        for t in topics
    ]

    for event in events:
        event_keywords = {k.lower() for k in (event.entities or [])}
        centroid = list(event.centroid) if event.centroid is not None else None
        matches = [(v.id, score_topic(event_keywords, centroid, v)) for v in views]

        # Replace this event's topic links — keep only the top-K most relevant
        # (e5 gives moderate similarity to many topics, so cap for a clean signal).
        await session.execute(delete(EventTopic).where(EventTopic.event_id == event.id))
        kept = sorted(
            (m for m in matches if m[1] >= min_relevance), key=lambda m: m[1], reverse=True
        )[:top_k]
        for topic_id, rel in kept:
            session.add(EventTopic(event_id=event.id, topic_id=topic_id, relevance=rel))

        event.personal_relevance = best_relevance(matches)
