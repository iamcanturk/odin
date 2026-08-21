"""Small management CLI: seed default sources and run a one-off ingestion.

  uv run python -m app.scripts.manage seed
  uv run python -m app.scripts.manage ingest
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.models import ContentCandidate, ContentItem, Event, Notification, Source
from app.models.associations import EventSource, EventTopic
from app.models.enums import EventStatus, Priority, SourceType
from app.pipeline.cost import persist_usage
from app.pipeline.enrich import apply_enrichment
from app.pipeline.ingest import build_adapter, run_ingestion
from app.pipeline.opportunity import apply_opportunity
from app.pipeline.retention import purge_old_content
from app.pipeline.style import build_style_profile
from app.pipeline.topics import apply_topic_matching
from app.providers.factory import get_embedding_provider, get_llm_provider

DEFAULT_SOURCES = [
    {"name": "Hacker News", "type": SourceType.HACKERNEWS, "url": None, "category": "technology",
     "priority": Priority.HIGH, "confidence": 0.6},
    {"name": "Ars Technica", "type": SourceType.RSS,
     "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "technology",
     "priority": Priority.MEDIUM, "confidence": 0.9},
    {"name": "The Verge", "type": SourceType.RSS, "url": "https://www.theverge.com/rss/index.xml",
     "category": "technology", "priority": Priority.MEDIUM, "confidence": 0.85},
    # Security / CVE / breaches / outages
    {"name": "BleepingComputer", "type": SourceType.RSS,
     "url": "https://www.bleepingcomputer.com/feed/", "category": "security",
     "priority": Priority.HIGH, "confidence": 0.9},
    {"name": "The Hacker News", "type": SourceType.RSS,
     "url": "https://feeds.feedburner.com/TheHackersNews", "category": "security",
     "priority": Priority.HIGH, "confidence": 0.85},
    {"name": "Krebs on Security", "type": SourceType.RSS,
     "url": "https://krebsonsecurity.com/feed/", "category": "security",
     "priority": Priority.HIGH, "confidence": 0.95},
    {"name": "SecurityWeek", "type": SourceType.RSS,
     "url": "https://www.securityweek.com/feed/", "category": "security",
     "priority": Priority.MEDIUM, "confidence": 0.88},
    # CVEs. KEV is the high-signal one: vulnerabilities under ACTIVE exploitation, not
    # the thousands published monthly that nobody ever attacks.
    {"name": "CISA Known Exploited Vulns", "type": SourceType.CISA_KEV, "url": None,
     "category": "cve", "priority": Priority.HIGH, "confidence": 0.98},
    {"name": "High-severity CVEs", "type": SourceType.RSS,
     "url": "https://cvefeed.io/rssfeed/severity/high.xml", "category": "cve",
     "priority": Priority.MEDIUM, "confidence": 0.75},
    # Turkish tech sources
    {"name": "Webtekno", "type": SourceType.RSS, "url": "https://www.webtekno.com/rss.xml",
     "category": "technology", "priority": Priority.MEDIUM, "confidence": 0.8},
    {"name": "ShiftDelete", "type": SourceType.RSS, "url": "https://shiftdelete.net/feed",
     "category": "technology", "priority": Priority.MEDIUM, "confidence": 0.8},
    {"name": "Donanım Haber", "type": SourceType.RSS,
     "url": "https://www.donanimhaber.com/rss/tum/", "category": "technology",
     "priority": Priority.MEDIUM, "confidence": 0.78},
    {"name": "Teknoblog", "type": SourceType.RSS, "url": "https://www.teknoblog.com/feed/",
     "category": "technology", "priority": Priority.MEDIUM, "confidence": 0.78},
    # Google Trends (trending searches) — TR + global
    {"name": "Google Trends TR", "type": SourceType.RSS,
     "url": "https://trends.google.com/trending/rss?geo=TR", "category": "trends",
     "priority": Priority.HIGH, "confidence": 0.7},
    {"name": "Google Trends US", "type": SourceType.RSS,
     "url": "https://trends.google.com/trending/rss?geo=US", "category": "trends",
     "priority": Priority.MEDIUM, "confidence": 0.65},
    # AI labs / models / tools / benchmarks
    {"name": "OpenAI", "type": SourceType.RSS, "url": "https://openai.com/news/rss.xml",
     "category": "ai", "priority": Priority.HIGH, "confidence": 0.95},
    {"name": "Google AI Blog", "type": SourceType.RSS,
     "url": "https://blog.google/technology/ai/rss/", "category": "ai",
     "priority": Priority.HIGH, "confidence": 0.9},
    {"name": "Google DeepMind", "type": SourceType.RSS,
     "url": "https://deepmind.google/blog/rss.xml", "category": "ai",
     "priority": Priority.HIGH, "confidence": 0.9},
    {"name": "Hugging Face", "type": SourceType.RSS, "url": "https://huggingface.co/blog/feed.xml",
     "category": "ai", "priority": Priority.HIGH, "confidence": 0.88},
    {"name": "Simon Willison", "type": SourceType.RSS,
     "url": "https://simonwillison.net/atom/everything/", "category": "ai",
     "priority": Priority.HIGH, "confidence": 0.9},
    {"name": "TechCrunch AI", "type": SourceType.RSS,
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "ai",
     "priority": Priority.MEDIUM, "confidence": 0.82},
    {"name": "AI News", "type": SourceType.RSS,
     "url": "https://www.artificialintelligence-news.com/feed/", "category": "ai",
     "priority": Priority.MEDIUM, "confidence": 0.78},
    {"name": "Cursor Changelog", "type": SourceType.RSS,
     "url": "https://www.cursor.com/changelog/rss.xml", "category": "devtools",
     "priority": Priority.MEDIUM, "confidence": 0.85},
    # Reddit — blocked for datacenter IPs, so the extension relays these from the
    # browser's residential IP via POST /ingest/feed. type=rss so the same parser applies.
    {"name": "Reddit r/programming", "type": SourceType.RSS,
     "url": "https://www.reddit.com/r/programming/.rss", "category": "technology",
     "priority": Priority.MEDIUM, "confidence": 0.7, "enabled": False},
    {"name": "Reddit r/devops", "type": SourceType.RSS,
     "url": "https://www.reddit.com/r/devops/.rss", "category": "devtools",
     "priority": Priority.MEDIUM, "confidence": 0.7, "enabled": False},
    {"name": "Reddit r/selfhosted", "type": SourceType.RSS,
     "url": "https://www.reddit.com/r/selfhosted/.rss", "category": "devtools",
     "priority": Priority.MEDIUM, "confidence": 0.7, "enabled": False},
    {"name": "Reddit r/netsec", "type": SourceType.RSS,
     "url": "https://www.reddit.com/r/netsec/.rss", "category": "security",
     "priority": Priority.HIGH, "confidence": 0.8, "enabled": False},
    {"name": "Reddit r/LocalLLaMA", "type": SourceType.RSS,
     "url": "https://www.reddit.com/r/LocalLLaMA/.rss", "category": "ai",
     "priority": Priority.HIGH, "confidence": 0.75, "enabled": False},
    # Pinterest — visual references for post imagery.
    {"name": "Pinterest Trends", "type": SourceType.RSS,
     "url": "https://www.pinterest.com/pinterest/official-news.rss", "category": "visual",
     "priority": Priority.LOW, "confidence": 0.4},
    # Outages / platform status
    {"name": "Google Search Status", "type": SourceType.RSS,
     "url": "https://status.search.google.com/en/feed.atom", "category": "status",
     "priority": Priority.HIGH, "confidence": 0.95},
]


async def seed() -> None:
    async with async_session_factory() as session:
        existing = {
            n for (n,) in (await session.execute(select(Source.name))).all()
        }
        added = 0
        for spec in DEFAULT_SOURCES:
            if spec["name"] in existing:
                continue
            session.add(Source(**spec))
            added += 1
        await session.commit()
        print(f"seeded {added} new source(s); {len(existing)} already present")


async def ingest() -> None:
    async with async_session_factory() as session:
        stats = await run_ingestion(
            session, get_embedding_provider(), llm=get_llm_provider()
        )
    print(
        f"polled={stats.sources_polled} items={stats.items_created} "
        f"events_created={stats.events_created} events_updated={stats.events_updated} "
        f"errors={stats.errors}"
    )


async def rematch() -> None:
    """Re-run topic matching over all non-archived events (e.g. after editing topics)."""
    async with async_session_factory() as session:
        events = list(
            (
                await session.execute(
                    select(Event).where(Event.status != EventStatus.ARCHIVED)
                )
            ).scalars()
        )
        await apply_topic_matching(session, events, get_embedding_provider())
        await apply_opportunity(session, events, now=datetime.now(UTC))
        await session.commit()
        print(f"rematched {len(events)} events")


async def style() -> None:
    """Recompute the writing-style fingerprint from imported posts."""
    async with async_session_factory() as session:
        profile = await build_style_profile(
            session, get_embedding_provider(), llm=get_llm_provider()
        )
        await session.commit()
        print(f"style profile rebuilt from {profile.post_count} posts: {profile.summary}")


async def enrich() -> None:
    """Backfill LLM summaries (in CONTENT_LANGUAGE) for current share-worthy events."""
    settings = get_settings()
    async with async_session_factory() as session:
        events = list(
            (
                await session.execute(
                    select(Event).where(Event.status != EventStatus.ARCHIVED)
                )
            ).scalars()
        )
        n = await apply_enrichment(
            session,
            events,
            get_llm_provider(),
            threshold=settings.enrich_trend_threshold,
            language=settings.content_language,
        )
        await persist_usage(session, purpose="enrich")
        await session.commit()
        print(f"enriched {n} of {len(events)} events in {settings.content_language}")


async def backfill_media() -> None:
    """Re-fetch every feed and attach images to items we already stored.

    Image extraction was added after most items were ingested, and conditional GET means
    those feeds return 304 forever — so the only way to fill them in is a forced re-fetch
    matched back onto existing rows by content_hash.
    """
    async with async_session_factory() as session:
        sources = list(
            (
                await session.execute(
                    select(Source).where(Source.enabled.is_(True), Source.type == SourceType.RSS)
                )
            ).scalars()
        )
        updated = 0
        for source in sources:
            adapter = build_adapter(source)
            if adapter is None:
                continue
            try:
                result = await adapter.fetch()  # no etag/last-modified: force a full body
            except Exception as exc:  # noqa: BLE001 - one bad feed shouldn't stop the rest
                print(f"  {source.name}: {exc}")
                continue
            if result.status != "ok":
                print(f"  {source.name}: {result.error}")
                continue

            by_hash = {i.content_hash: i for i in result.items if i.media}
            if not by_hash:
                continue
            rows = list(
                (
                    await session.execute(
                        select(ContentItem).where(ContentItem.content_hash.in_(by_hash))
                    )
                ).scalars()
            )
            for item in rows:
                if not item.media:
                    item.media = by_hash[item.content_hash].media
                    updated += 1
        await session.commit()
        print(f"backfilled images on {updated} item(s) across {len(sources)} feed(s)")


async def purge_old() -> None:
    """Apply the retention window now instead of waiting for the nightly job."""
    settings = get_settings()
    async with async_session_factory() as session:
        stats = await purge_old_content(session, days=settings.retention_days)
    print(
        f"purged {stats.items} item(s), {stats.events} event(s), "
        f"{stats.observed} observed tweet(s) older than {settings.retention_days}d"
    )


async def purge_events() -> None:
    """One-time cleanup: wipe all events + ingested items so the console starts fresh.

    Keeps sources, topics, imported posts, profile snapshots and the style profile.
    """
    async with async_session_factory() as session:
        n_events = await session.scalar(select(func.count(Event.id))) or 0
        n_items = await session.scalar(select(func.count(ContentItem.id))) or 0
        # Order matters: candidates/associations FK-cascade on events, but content_items
        # only SET NULL, so delete them explicitly. Notifications reference events by id.
        await session.execute(delete(ContentCandidate))
        await session.execute(delete(EventTopic))
        await session.execute(delete(EventSource))
        await session.execute(delete(ContentItem))
        await session.execute(delete(Notification))
        await session.execute(delete(Event))
        await session.commit()
        print(f"purged {n_events} events and {n_items} content items")


async def _dispatch(command: str) -> None:
    await {
        "seed": seed,
        "ingest": ingest,
        "rematch": rematch,
        "style": style,
        "enrich": enrich,
        "backfill-media": backfill_media,
        "purge-old": purge_old,
        "purge-events": purge_events,
    }[command]()


def main() -> None:
    parser = argparse.ArgumentParser(description="ODIN management commands")
    parser.add_argument(
        "command",
        choices=[
            "seed", "ingest", "rematch", "style", "enrich",
            "backfill-media", "purge-old", "purge-events",
        ],
    )
    args = parser.parse_args()
    asyncio.run(_dispatch(args.command))


if __name__ == "__main__":
    main()
