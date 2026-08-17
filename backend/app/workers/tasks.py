"""ARQ worker: scheduled source ingestion.

Run with:  uv run arq app.workers.tasks.WorkerSettings
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.pipeline.ingest import run_ingestion
from app.providers.factory import get_embedding_provider

log = get_logger("odin.worker")


async def poll_sources(ctx: dict[str, Any]) -> dict[str, Any]:
    async with async_session_factory() as session:
        stats = await run_ingestion(session, get_embedding_provider())
    return {
        "sources_polled": stats.sources_polled,
        "items_created": stats.items_created,
        "events_created": stats.events_created,
        "events_updated": stats.events_updated,
        "errors": stats.errors,
    }


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)
    log.info("worker.startup")


class WorkerSettings:
    functions = [poll_sources]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Poll every 15 minutes.
    cron_jobs = [cron(poll_sources, minute={0, 15, 30, 45})]
