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
from app.pipeline.ingest import process_pending, run_ingestion
from app.providers.factory import get_embedding_provider, get_llm_provider

log = get_logger("odin.worker")


async def poll_sources(ctx: dict[str, Any]) -> dict[str, Any]:
    async with async_session_factory() as session:
        stats = await run_ingestion(
            session, get_embedding_provider(), llm=get_llm_provider()
        )
    return {
        "sources_polled": stats.sources_polled,
        "items_created": stats.items_created,
        "events_created": stats.events_created,
        "events_updated": stats.events_updated,
        "errors": stats.errors,
    }


async def process_inbound(ctx: dict[str, Any]) -> dict[str, Any]:
    """Process inbound (browser-extension) items the API stored without embedding."""
    async with async_session_factory() as session:
        stats = await process_pending(
            session, get_embedding_provider(), llm=get_llm_provider()
        )
    return {"items": stats.items_created, "events_created": stats.events_created}


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)
    log.info("worker.startup")


class WorkerSettings:
    functions = [poll_sources, process_inbound]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs = [
        cron(poll_sources, minute={0, 15, 30, 45}),  # poll sources every 15 min
        cron(process_inbound, second={0, 30}),  # process inbound items ~every 30s
    ]
