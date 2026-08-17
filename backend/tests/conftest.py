"""Shared test fixtures.

`db_sessionmaker` provisions an **isolated throwaway database** (`odin_pytest`) with
the schema applied, so integration tests never touch dev data and stay deterministic.
Skips cleanly when Postgres isn't reachable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (register models on Base.metadata)
from app.core.config import get_settings
from app.core.db import Base

TEST_DB = "odin_pytest"


def _swap_db(url: str, dbname: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{dbname}"


@pytest.fixture
async def db_sessionmaker():
    settings = get_settings()
    admin_url = _swap_db(settings.database_url, "postgres")

    try:
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE {TEST_DB}'))
        await admin.dispose()
    except Exception:  # noqa: BLE001
        pytest.skip("postgres not available")

    engine = create_async_engine(_swap_db(settings.database_url, TEST_DB))
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)'))
    await admin.dispose()
