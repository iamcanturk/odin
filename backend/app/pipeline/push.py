"""Deliver notifications to Telegram (PROJECT.md §32).

Notifications that live only in a web app you have to remember to open aren't
notifications. This mirrors unsent ones to Telegram, marks them delivered, and — for
anything with text you might actually post — attaches a one-tap link that opens X
with the draft already filled in.

Failure is non-fatal by design: an unreachable Telegram must never break the cron
that produced the notification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Event, Notification, Post
from app.providers.telegram import TelegramClient, intent_url

# Anything older than this is history; pushing it is noise.
FRESH_WINDOW = timedelta(hours=12)
MAX_PER_RUN = 8

SEVERITY_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


@dataclass
class PushStats:
    sent: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _format(notification: Notification) -> str:
    icon = SEVERITY_ICON.get(notification.severity, "🔵")
    parts = [f"{icon} <b>{_escape(notification.title)}</b>"]
    if notification.body:
        parts.append(_escape(notification.body))
    return "\n\n".join(parts)


def _escape(text: str) -> str:
    """Telegram's HTML mode: only these three need escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _buttons(session: AsyncSession, notification: Notification) -> list[tuple[str, str]]:
    """A post link when there's something to post, plus the event on the web UI."""
    buttons: list[tuple[str, str]] = []

    if notification.type == "post_due" and notification.body:
        # The reminder body IS the draft text.
        buttons.append(("𝕏 Paylaş", intent_url(notification.body)))
    elif notification.event_id is not None:
        draft = (
            await session.execute(
                select(Post)
                .where(Post.event_id == notification.event_id, Post.status != "posted")
                .order_by(Post.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if draft is not None:
            buttons.append(("𝕏 Paylaş", intent_url(draft.text)))

    if notification.event_id is not None:
        event = await session.get(Event, notification.event_id)
        if event is not None:
            base = get_settings().public_base_url.rstrip("/")
            buttons.append(("ODIN'de aç", f"{base}/events/{event.id}"))

    return buttons


async def push_pending(
    session: AsyncSession,
    telegram: TelegramClient,
    *,
    now: datetime | None = None,
    limit: int = MAX_PER_RUN,
) -> PushStats:
    """Mirror undelivered, still-fresh notifications to Telegram."""
    stats = PushStats()
    if not telegram.configured:
        return stats

    now = now or datetime.now(UTC)
    pending = list(
        (
            await session.execute(
                select(Notification)
                .where(
                    Notification.pushed_at.is_(None),
                    Notification.created_at >= now - FRESH_WINDOW,
                )
                .order_by(Notification.created_at.asc())
                .limit(limit)
            )
        ).scalars()
    )
    if not pending:
        return stats

    async with httpx.AsyncClient(timeout=15.0) as client:
        for notification in pending:
            result = await telegram.send(
                _format(notification),
                buttons=await _buttons(session, notification),
                client=client,
            )
            if result.ok:
                # Stamped only on success, so a Telegram outage retries rather than
                # silently swallowing the alert.
                notification.pushed_at = now
                stats.sent += 1
            else:
                stats.errors.append(result.error or "unknown")

    await session.flush()
    return stats
