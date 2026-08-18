"""Ingestion pipeline: poll sources -> store ContentItems -> embed -> cluster -> score.

Orchestrates the tested building blocks (adapters, embeddings, clustering, trend)
against the database. Designed to be idempotent: re-running never duplicates items
(dedup on content_hash) and re-scores events from their current mentions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import ContentItem, Event, Source
from app.models.enums import EventStatus
from app.pipeline.clustering import (
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW,
    Cluster,
    ClusterItem,
    score,
)
from app.pipeline.enrich import apply_enrichment
from app.pipeline.notify import emit_for_events, emit_for_sources, emit_trend_spikes
from app.pipeline.opportunity import apply_opportunity
from app.pipeline.text import keywords
from app.pipeline.topics import apply_topic_matching
from app.pipeline.trend import Mention, advance_status, compute_trend
from app.providers.base import EmbeddingProvider, LLMProvider
from app.sources.base import SourceAdapter
from app.sources.github import GitHubAdapter
from app.sources.hackernews import HackerNewsAdapter
from app.sources.reddit import RedditAdapter, parse_subreddits
from app.sources.rss import RSSAdapter

log = get_logger("odin.ingest")

RECENT_DAYS = 3


@dataclass
class IngestStats:
    sources_polled: int = 0
    items_created: int = 0
    events_created: int = 0
    events_updated: int = 0
    errors: list[str] = field(default_factory=list)


def build_adapter(source: Source) -> SourceAdapter | None:
    if source.type == "rss" and source.url:
        return RSSAdapter(source.url, name=source.name)
    if source.type == "hackernews":
        return HackerNewsAdapter()
    if source.type == "reddit":
        # source.url holds the subreddit spec, e.g. "programming+technology".
        return RedditAdapter(parse_subreddits(source.url))
    if source.type == "github":
        return GitHubAdapter()
    return None


def _item_text(item: ContentItem) -> str:
    return " ".join(p for p in (item.title, item.text) if p).strip()


async def _existing_hashes(session: AsyncSession, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    rows = await session.execute(
        select(ContentItem.content_hash).where(ContentItem.content_hash.in_(hashes))
    )
    return {r[0] for r in rows}


async def poll_source(
    session: AsyncSession, source: Source, stats: IngestStats
) -> list[ContentItem]:
    """Fetch one source and persist new ContentItems. Updates source health."""
    adapter = build_adapter(source)
    now = datetime.now(UTC)
    source.last_polled_at = now
    if adapter is None:
        stats.errors.append(f"{source.name}: no adapter for type {source.type}")
        return []

    result = await adapter.fetch(etag=source.etag, last_modified=source.last_modified)
    if result.status != "ok":
        source.failure_count += 1
        stats.errors.append(f"{source.name}: {result.error}")
        return []

    source.last_success_at = now
    source.failure_count = 0
    if result.etag:
        source.etag = result.etag
    if result.last_modified:
        source.last_modified = result.last_modified
    if result.not_modified:
        return []

    known = await _existing_hashes(session, [i.content_hash for i in result.items])
    created: list[ContentItem] = []
    for norm in result.items:
        if norm.content_hash in known:
            continue
        known.add(norm.content_hash)
        item = ContentItem(
            source_id=source.id,
            source_item_id=norm.source_item_id,
            url=norm.url,
            content_hash=norm.content_hash,
            title=norm.title,
            text=norm.text,
            author=norm.author,
            published_at=norm.published_at,
            language=norm.language,
            media=norm.media,
            engagement=norm.engagement,
            item_metadata=norm.metadata,
        )
        session.add(item)
        created.append(item)

    stats.items_created += len(created)
    await session.flush()
    return created


async def embed_items(items: list[ContentItem], embedder: EmbeddingProvider) -> None:
    targets = [it for it in items if it.embedding is None and _item_text(it)]
    if not targets:
        return
    vectors = await embedder.embed_texts([_item_text(it) for it in targets])
    for item, vector in zip(targets, vectors, strict=False):
        item.embedding = vector


def _event_to_cluster(event: Event) -> Cluster:
    cluster = Cluster(
        centroid=list(event.centroid) if event.centroid is not None else None,
        keywords=set(event.entities or []),
        first_seen=event.first_seen_at,
        last_seen=event.last_seen_at,
    )
    return cluster


async def assign_events(
    session: AsyncSession,
    items: list[ContentItem],
    stats: IngestStats,
    *,
    now: datetime,
    threshold: float = DEFAULT_THRESHOLD,
) -> set[Event]:
    """Attach each new item to a matching recent Event or create a new one."""
    window_start = now - DEFAULT_WINDOW
    rows = await session.execute(
        select(Event).where(
            Event.last_seen_at >= window_start, Event.status != EventStatus.ARCHIVED
        )
    )
    events = list(rows.scalars())
    clusters: dict[Event, Cluster] = {e: _event_to_cluster(e) for e in events}
    affected: set[Event] = set()

    for item in items:
        ci = ClusterItem(
            id=str(item.id),
            title=item.title,
            embedding=list(item.embedding) if item.embedding is not None else None,
            keywords=keywords(_item_text(item)),
            url=item.url,
            timestamp=item.published_at or item.created_at or now,
        )
        best_event, best_score = None, 0.0
        for event, cluster in clusters.items():
            s = score(ci, cluster, DEFAULT_WINDOW)
            if s > best_score:
                best_score, best_event = s, event

        if best_event is not None and best_score >= threshold:
            event = best_event
            stats.events_updated += 1
        else:
            event = Event(
                title=item.title or "Untitled event",
                status=EventStatus.DISCOVERED,
                first_seen_at=ci.timestamp,
                last_seen_at=ci.timestamp,
                entities=[],
                centroid=ci.embedding,
            )
            session.add(event)
            await session.flush()
            events.append(event)
            clusters[event] = _event_to_cluster(event)
            stats.events_created += 1

        _attach(event, clusters[event], item, ci, now)
        affected.add(event)

    return affected


def _attach(
    event: Event, cluster: Cluster, item: ContentItem, ci: ClusterItem, now: datetime
) -> None:
    cluster.add(ci)
    item.event = event
    event.centroid = cluster.centroid
    event.entities = sorted(cluster.keywords)
    event.first_seen_at = min(event.first_seen_at, ci.timestamp)
    event.last_seen_at = max(event.last_seen_at, ci.timestamp)


async def score_events(
    session: AsyncSession, events: set[Event], stats: IngestStats, *, now: datetime
) -> None:
    for event in events:
        rows = await session.execute(
            select(ContentItem, Source)
            .join(Source, ContentItem.source_id == Source.id)
            .where(ContentItem.event_id == event.id)
        )
        mentions: list[Mention] = []
        source_names: set[str] = set()
        recent_count = 0
        for item, src in rows:
            ts = item.published_at or item.created_at or now
            eng = float(item.engagement.get("points") or 0) if item.engagement else 0.0
            mentions.append(
                Mention(timestamp=ts, source_type=src.type, source_name=src.name, engagement=eng)
            )
            source_names.add(src.name)
            if ts >= now - timedelta(hours=1):
                recent_count += 1

        result = compute_trend(mentions, now=now)
        event.trend_score = result.trend_score
        event.velocity = result.components
        event.scoring_version = result.scoring_version
        age_hours = (now - event.first_seen_at).total_seconds() / 3600
        event.status = advance_status(
            event.status,
            result,
            source_count=len(source_names),
            recent_count=recent_count,
            age_hours=age_hours,
        )


async def process_new_items(
    session: AsyncSession,
    new_items: list[ContentItem],
    embedder: EmbeddingProvider,
    stats: IngestStats,
    *,
    llm: LLMProvider | None = None,
    now: datetime,
) -> set[Event]:
    """Shared post-ingest pipeline: embed → cluster → score → topics → opportunity → enrich.

    Used by both polled ingestion and inbound (browser-extension) ingestion. Does NOT
    commit — the caller controls the transaction.
    """
    await embed_items(new_items, embedder)
    affected = await assign_events(session, new_items, stats, now=now)
    await score_events(session, affected, stats, now=now)
    await apply_topic_matching(session, list(affected), embedder)
    await apply_opportunity(session, list(affected), now=now)
    if llm is not None:
        settings = get_settings()
        await apply_enrichment(
            session,
            list(affected),
            llm,
            threshold=settings.enrich_trend_threshold,
            language=settings.content_language,
        )
    return affected


async def process_pending(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    llm: LLMProvider | None = None,
    now: datetime | None = None,
    limit: int = 300,
) -> IngestStats:
    """Process content items not yet assigned to an event (e.g. inbound extension items).

    Runs the shared pipeline on unprocessed items, so POST /ingest/x can return
    immediately and the worker catches up within a minute.
    """
    now = now or datetime.now(UTC)
    stats = IngestStats()
    pending = list(
        (
            await session.execute(
                select(ContentItem).where(ContentItem.event_id.is_(None)).limit(limit)
            )
        ).scalars()
    )
    if not pending:
        return stats
    stats.items_created = len(pending)
    affected = await process_new_items(session, pending, embedder, stats, llm=llm, now=now)
    await emit_for_events(session, list(affected))
    await emit_trend_spikes(session, list(affected))
    await session.commit()
    log.info("process_pending.done", items=len(pending), events_created=stats.events_created)
    return stats


async def run_ingestion(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    llm: LLMProvider | None = None,
    now: datetime | None = None,
) -> IngestStats:
    now = now or datetime.now(UTC)
    stats = IngestStats()

    sources = list(
        (await session.execute(select(Source).where(Source.enabled.is_(True)))).scalars()
    )
    all_new: list[ContentItem] = []
    for source in sources:
        stats.sources_polled += 1
        try:
            all_new.extend(await poll_source(session, source, stats))
        except Exception as exc:  # noqa: BLE001 - record and continue other sources
            stats.errors.append(f"{source.name}: {exc}")

    affected = await process_new_items(session, all_new, embedder, stats, llm=llm, now=now)
    await emit_for_events(session, list(affected))
    await emit_trend_spikes(session, list(affected))
    await emit_for_sources(session, sources)
    await session.commit()

    log.info(
        "ingest.done",
        sources=stats.sources_polled,
        items=stats.items_created,
        events_created=stats.events_created,
        errors=len(stats.errors),
    )
    return stats
