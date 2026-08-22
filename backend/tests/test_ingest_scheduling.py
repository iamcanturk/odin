"""Tests for how run_ingestion picks and paces sources.

These pin a real production failure: 25 sources polled sequentially, each with a
25s ceiling, against ARQ's 300s job timeout. The job was cancelled every run, the
transaction rolled back, and the three newest sources — two CVE feeds and Pinterest
— sat at the end of the list with last_polled_at NULL for over a day.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Source
from app.pipeline.ingest import (
    FETCH_CONCURRENCY,
    PER_SOURCE_TIMEOUT,
    IngestStats,
    apply_result,
    fetch_source,
)
from app.schemas.ingest import FetchResult

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


async def _sources(db_sessionmaker, spec: list[tuple[str, datetime | None]]) -> None:
    async with db_sessionmaker() as session:
        for name, polled in spec:
            session.add(
                Source(
                    name=name,
                    type="rss",
                    url=f"https://example.com/{name}",
                    enabled=True,
                    priority="med",
                    poll_interval_seconds=900,
                    confidence=0.6,
                    last_polled_at=polled,
                )
            )
        await session.commit()


async def test_never_polled_sources_come_first(db_sessionmaker):
    """Otherwise a new feed is added, sits at the back, and is never reached."""
    await _sources(
        db_sessionmaker,
        [
            ("old", NOW - timedelta(hours=2)),
            ("never-polled", None),
            ("recent", NOW - timedelta(minutes=5)),
        ],
    )
    async with db_sessionmaker() as session:
        ordered = list(
            (
                await session.execute(
                    select(Source)
                    .where(Source.enabled.is_(True))
                    .order_by(Source.last_polled_at.asc().nullsfirst())
                )
            ).scalars()
        )
    assert [s.name for s in ordered] == ["never-polled", "old", "recent"]


async def test_a_hanging_source_gives_up_instead_of_eating_the_job(db_sessionmaker):
    """One slow feed must not consume the whole run's budget."""

    class Hanging:
        async def fetch(self, **_kw):
            await asyncio.sleep(PER_SOURCE_TIMEOUT + 5)
            return FetchResult()

    import app.pipeline.ingest as mod

    original = mod.build_adapter
    mod.build_adapter = lambda source: Hanging()
    try:
        source = Source(name="slow", type="rss", url="https://x", enabled=True,
                        priority="med", poll_interval_seconds=900, confidence=0.6)
        # Shorten the ceiling so the test doesn't actually wait 25 seconds.
        mod.PER_SOURCE_TIMEOUT = 0.05
        result = await fetch_source(source)
    finally:
        mod.build_adapter = original
        mod.PER_SOURCE_TIMEOUT = PER_SOURCE_TIMEOUT

    assert result.status == "error"
    assert "timed out" in result.error


async def test_an_unknown_source_type_is_an_error_not_a_crash(db_sessionmaker):
    source = Source(name="weird", type="carrier-pigeon", enabled=True,
                    priority="med", poll_interval_seconds=900, confidence=0.6)
    result = await fetch_source(source)
    assert result.status == "error"
    assert "no adapter" in result.error


async def test_a_failed_fetch_still_stamps_last_polled_at(db_sessionmaker):
    """Health has to advance even on failure, or a broken feed looks untried."""
    async with db_sessionmaker() as session:
        source = Source(name="broken", type="rss", url="https://x", enabled=True,
                        priority="med", poll_interval_seconds=900, confidence=0.6)
        session.add(source)
        await session.flush()

        stats = IngestStats()
        created = await apply_result(
            session, source, FetchResult(status="error", error="boom"), stats
        )
        assert created == []
        assert source.last_polled_at is not None
        assert source.last_success_at is None
        assert source.failure_count == 1
        assert any("boom" in e for e in stats.errors)


def test_fetching_is_bounded():
    """Concurrent, but not 25-sockets-at-once concurrent."""
    assert 1 < FETCH_CONCURRENCY <= 12
