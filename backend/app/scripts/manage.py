"""Small management CLI: seed default sources and run a one-off ingestion.

  uv run python -m app.scripts.manage seed
  uv run python -m app.scripts.manage ingest
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.models import Source
from app.models.enums import Priority, SourceType
from app.pipeline.ingest import run_ingestion
from app.providers.factory import get_embedding_provider

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
        stats = await run_ingestion(session, get_embedding_provider())
    print(
        f"polled={stats.sources_polled} items={stats.items_created} "
        f"events_created={stats.events_created} events_updated={stats.events_updated} "
        f"errors={stats.errors}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ODIN management commands")
    parser.add_argument("command", choices=["seed", "ingest"])
    args = parser.parse_args()
    asyncio.run(seed() if args.command == "seed" else ingest())


if __name__ == "__main__":
    main()
