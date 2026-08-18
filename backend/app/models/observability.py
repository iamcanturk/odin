"""Observability: LLM cost tracking + pipeline run logs (PROJECT.md §34, §44)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import uuid_pk


class LlmUsage(Base):
    """One row per LLM call — tokens + estimated cost."""

    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = uuid_pk()
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )


class RunLog(Base):
    """One row per pipeline run (poll / inbound) for the System log."""

    __tablename__ = "run_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # poll | inbound
    sources_polled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )
