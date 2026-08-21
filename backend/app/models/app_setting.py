"""User-editable settings that shouldn't need a redeploy to change."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk


class AppSetting(Base, TimestampMixin):
    """A single key/value pair. Env vars stay for secrets and infrastructure."""

    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
