"""Guard against migration/model drift.

The suite builds its schema with Base.metadata.create_all; production builds it by
running migrations. When the two disagree every test passes and production breaks —
which is exactly what happened: app_settings' timestamps carried
server_default=func.now() on the model and NOT NULL with no default in the
migration, so the table could not accept a single insert in production.

This runs the real migration chain against a throwaway database and asks alembic to
diff the result against the models.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import Base

MIGRATION_DB = "odin_migrations_test"

# compare_metadata reports these for pgvector columns because the extension type
# doesn't round-trip to an identical Python object. Not real drift.
IGNORED_OPS = ("modify_type",)


def _swap_db(url: str, db: str) -> str:
    return url.rsplit("/", 1)[0] + f"/{db}"


@pytest.fixture
async def migrated_url():
    settings = get_settings()
    admin_url = _swap_db(settings.database_url, "postgres")

    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {MIGRATION_DB} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {MIGRATION_DB}"))
    await admin.dispose()

    url = _swap_db(settings.database_url, MIGRATION_DB)
    # A subprocess so alembic's env.py resolves the URL its own way, exactly as it
    # does on the server — testing the real path rather than a reimplementation.
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
        env={**os.environ, "DATABASE_URL": url},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _out, err = await process.communicate()
    assert process.returncode == 0, f"alembic upgrade failed:\n{err.decode()[-2000:]}"

    yield url

    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {MIGRATION_DB} WITH (FORCE)"))
    await admin.dispose()


async def test_migrations_produce_the_schema_the_models_describe(migrated_url):
    engine = create_async_engine(migrated_url)
    try:
        async with engine.connect() as conn:
            diffs = await conn.run_sync(
                lambda sync_conn: compare_metadata(
                    MigrationContext.configure(sync_conn), Base.metadata
                )
            )
    finally:
        await engine.dispose()

    real = [d for d in diffs if not str(d[0]).startswith(IGNORED_OPS)]
    assert real == [], f"migrations drifted from models: {real}"


async def test_app_settings_accepts_an_insert_under_the_migrated_schema(migrated_url):
    """The exact production failure: NotNullViolation on created_at."""
    engine = create_async_engine(migrated_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app_settings (id, key, value) "
                    "VALUES (gen_random_uuid(), 'probe', '{\"value\": 1}'::jsonb)"
                )
            )
            row = (
                await conn.execute(text("SELECT created_at, updated_at FROM app_settings"))
            ).one()
    finally:
        await engine.dispose()

    assert row[0] is not None
    assert row[1] is not None
