"""Tests for observability: cost estimation + /system endpoint."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.core.db import get_session
from app.main import create_app
from app.models import LlmUsage, RunLog
from app.pipeline.cost import estimate_cost, persist_usage, record


@pytest.fixture
async def client(db_sessionmaker):
    async def _get_session():
        async with db_sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def test_estimate_cost_uses_configured_prices() -> None:
    # 1M in + 1M out at defaults (0.14 + 0.28) = 0.42
    assert estimate_cost(1_000_000, 1_000_000) == pytest.approx(0.42)
    assert estimate_cost(0, 0) == 0.0


async def test_persist_usage_writes_rows(db_sessionmaker) -> None:
    record("deepseek/deepseek-chat", 1000, 500)
    record("deepseek/deepseek-chat", 2000, 0)
    async with db_sessionmaker() as session:
        total = await persist_usage(session, purpose="enrich")
        await session.commit()
    assert total > 0
    async with db_sessionmaker() as session:
        rows = (await session.execute(__import__("sqlalchemy").select(LlmUsage))).scalars().all()
    assert len(rows) == 2
    assert all(r.purpose == "enrich" for r in rows)


async def test_system_endpoint_aggregates(db_sessionmaker, client: httpx.AsyncClient) -> None:
    async with db_sessionmaker() as session:
        session.add(
            LlmUsage(
                model="m", purpose="enrich", prompt_tokens=1000,
                completion_tokens=500, cost_usd=0.001,
            )
        )
        session.add(
            LlmUsage(
                model="m", purpose="generate", prompt_tokens=2000,
                completion_tokens=1000, cost_usd=0.002,
            )
        )
        session.add(
            RunLog(kind="poll", sources_polled=5, items_created=10, events_created=3, errors=[])
        )
        await session.commit()

    data = (await client.get("/api/v1/system")).json()
    assert data["calls_total"] == 2
    assert data["cost_total_usd"] == pytest.approx(0.003)
    assert data["tokens_total"] == 4500
    purposes = {b["purpose"]: b for b in data["by_purpose"]}
    assert purposes["enrich"]["calls"] == 1
    assert purposes["generate"]["cost_usd"] == pytest.approx(0.002)
    assert data["recent_runs"][0]["kind"] == "poll"
