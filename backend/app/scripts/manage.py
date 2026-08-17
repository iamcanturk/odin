"""Small management CLI: seed default sources and run a one-off ingestion.

  uv run python -m app.scripts.manage seed
  uv run python -m app.scripts.manage ingest
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import async_session_factory
from app.models import Event, Source
from app.models.enums import EventStatus, Priority, SourceType
from app.pipeline.ingest import run_ingestion
from app.pipeline.opportunity import apply_opportunity
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


async def _dispatch(command: str) -> None:
    await {"seed": seed, "ingest": ingest, "rematch": rematch}[command]()


def main() -> None:
    parser = argparse.ArgumentParser(description="ODIN management commands")
    parser.add_argument("command", choices=["seed", "ingest", "rematch"])
    args = parser.parse_args()
    asyncio.run(_dispatch(args.command))


if __name__ == "__main__":
    main()
