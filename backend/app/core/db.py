"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with async_session_factory() as session:
        yield session
