"""Deliver notifications to Telegram — sparingly (PROJECT.md §32).

The first version pushed everything unpushed, every ten minutes. In one day that
was 13 pings, including 23:00 and 04:00, for events scoring 46-49 out of 100. The
percentile threshold that decides "high opportunity" had collapsed to roughly the
median, so "high" meant "slightly above average" — not something worth reaching
into your pocket for.

So there are two channels now, and the split is the whole design:

  urgent  — rare, immediate, and carries a *finished tweet* with a one-tap post
            button. Must clear an absolute floor (not just a percentile), obey
            quiet hours, leave a minimum gap, and fit under a daily cap.
  digest  — everything else, once a day, as one compact message.

Queue reminders bypass all of it: you chose that time yourself, so it is not
ours to postpone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ContentCandidate, Event, Notification, Post
from app.pipeline.content import create_candidates
from app.providers.base import LLMProvider
from app.providers.telegram import TelegramClient, intent_url

log = structlog.get_logger(__name__)

# Interrupting you needs an absolute bar, not a relative one — a 90th percentile of a
# weak distribution is still weak. But 60 was set from the wrong distribution: scores
# topped out at 48 only because ingestion had been dying for a day, so events were
# stale and single-sourced. 45 sits just above the 46-49 band that was pinging all
# night, while still letting a genuinely hot event through. The daily cap and the
# 90-minute gap are what actually keep the volume down.
URGENT_FLOOR = 45.0
# Even above the floor: at most this many interruptions a day...
URGENT_DAILY_CAP = 3
# ...and never two in quick succession.
MIN_GAP = timedelta(minutes=90)
# Local hours during which nothing is pushed. 23:00-08:00.
QUIET_START, QUIET_END = 23, 8
# One digest a day, at this local hour.
DIGEST_HOUR = 9

# Anything older than this is history; pushing it is noise.
FRESH_WINDOW = timedelta(hours=12)
DIGEST_MAX_LINES = 12

REMINDER = "post_due"
HIGH_OPPORTUNITY = "high_opportunity"

SEVERITY_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


@dataclass
class PushStats:
    sent: int = 0
    digested: int = 0
    skipped_reason: str | None = None
    errors: list[str] = field(default_factory=list)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().push_timezone)
    except Exception:  # noqa: BLE001 - a bad tz name must not silence every alert
        log.warning("push.bad_timezone", value=get_settings().push_timezone)
        return ZoneInfo("UTC")


def local_hour(now: datetime) -> int:
    return now.astimezone(_tz()).hour


def in_quiet_hours(now: datetime) -> bool:
    """23:00-08:00 local. Wraps midnight, hence the `or`."""
    hour = local_hour(now)
    return hour >= QUIET_START or hour < QUIET_END


def _escape(text: str) -> str:
    """Telegram's HTML mode: only these three need escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _last_push(session: AsyncSession) -> datetime | None:
    value = (
        await session.execute(
            select(Notification.pushed_at)
            .where(Notification.pushed_at.is_not(None))
            .order_by(Notification.pushed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _pushed_today(session: AsyncSession, now: datetime) -> int:
    """Counted in *local* days, since the cap is about your day, not UTC's."""
    tz = _tz()
    midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    rows = list(
        (
            await session.execute(
                select(Notification.id).where(
                    Notification.pushed_at.is_not(None),
                    Notification.pushed_at >= midnight.astimezone(UTC),
                    Notification.type == HIGH_OPPORTUNITY,
                )
            )
        ).scalars()
    )
    return len(rows)


async def _pending(session: AsyncSession, now: datetime) -> list[Notification]:
    return list(
        (
            await session.execute(
                select(Notification)
                .where(
                    Notification.pushed_at.is_(None),
                    Notification.created_at >= now - FRESH_WINDOW,
                )
                .order_by(Notification.created_at.asc())
            )
        ).scalars()
    )


async def _draft_for(
    session: AsyncSession, event: Event, llm: LLMProvider | None
) -> Post | None:
    """A finished tweet to go with the alert.

    An alert that says "something happened, go write about it" still leaves you the
    work. This does the work first: reuse an existing candidate if the event already
    has one, otherwise generate, then persist it as a draft so it's waiting in the
    queue whether or not you tap Post.
    """
    existing = (
        await session.execute(
            select(ContentCandidate)
            .where(ContentCandidate.event_id == event.id)
            .order_by(ContentCandidate.rank.asc())
            .limit(1)
        )
    ).scalar_one_or_none()

    text: str | None = existing.text if existing else None
    if text is None:
        if llm is None:
            return None
        try:
            candidates = await create_candidates(
                session,
                event,
                llm,
                language=get_settings().content_language,
                angles=["insight"],
            )
        except Exception as exc:  # noqa: BLE001 - a generation failure must still alert
            log.warning("push.draft_failed", event=str(event.id), error=str(exc))
            return None
        if not candidates:
            return None
        text = candidates[0].text

    post = Post(
        platform="x",
        text=text,
        status="draft",
        origin="generated",
        angle="urgent",
        event_id=event.id,
    )
    session.add(post)
    await session.flush()
    return post


async def push_urgent(
    session: AsyncSession,
    telegram: TelegramClient,
    *,
    llm: LLMProvider | None = None,
    now: datetime | None = None,
) -> PushStats:
    """At most one interruption per run, and only when it has earned it."""
    stats = PushStats()
    if not telegram.configured:
        return stats
    now = now or datetime.now(UTC)

    pending = await _pending(session, now)
    if not pending:
        return stats

    # Queue reminders are exempt: you picked that time, so it isn't ours to postpone.
    reminders = [n for n in pending if n.type == REMINDER]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for reminder in reminders:
            result = await telegram.send(
                _format_reminder(reminder),
                buttons=[("𝕏 Paylaş", intent_url(reminder.body or ""))],
                client=client,
            )
            if result.ok:
                reminder.pushed_at = now
                stats.sent += 1
            else:
                stats.errors.append(result.error or "unknown")

        if in_quiet_hours(now):
            stats.skipped_reason = "quiet_hours"
            await session.flush()
            return stats

        last = await _last_push(session)
        if last is not None and now - last < MIN_GAP:
            stats.skipped_reason = "min_gap"
            await session.flush()
            return stats

        if await _pushed_today(session, now) >= URGENT_DAILY_CAP:
            stats.skipped_reason = "daily_cap"
            await session.flush()
            return stats

        # Of everything waiting, only the single best gets through — and only if it
        # clears the absolute floor. The rest fall through to the digest.
        best: tuple[float, Notification, Event] | None = None
        for n in pending:
            if n.type != HIGH_OPPORTUNITY or n.event_id is None:
                continue
            event = await session.get(Event, n.event_id)
            if event is None or event.opportunity_score < URGENT_FLOOR:
                continue
            if best is None or event.opportunity_score > best[0]:
                best = (event.opportunity_score, n, event)

        if best is None:
            stats.skipped_reason = "nothing_urgent"
            await session.flush()
            return stats

        score, notification, event = best
        draft = await _draft_for(session, event, llm)
        buttons: list[tuple[str, str]] = []
        if draft is not None:
            buttons.append(("𝕏 Paylaş", intent_url(draft.text)))
        base = get_settings().public_base_url.rstrip("/")
        buttons.append(("ODIN'de aç", f"{base}/events/{event.id}"))

        result = await telegram.send(
            _format_urgent(event, score, draft), buttons=buttons, client=client
        )
        if result.ok:
            notification.pushed_at = now
            stats.sent += 1
        else:
            stats.errors.append(result.error or "unknown")

    await session.flush()
    return stats


async def _best_event(
    session: AsyncSession, pending: list[Notification]
) -> Event | None:
    """Highest-scoring event among what's waiting."""
    best: Event | None = None
    for n in pending:
        if n.event_id is None:
            continue
        event = await session.get(Event, n.event_id)
        if event is None:
            continue
        if best is None or event.opportunity_score > best.opportunity_score:
            best = event
    return best


def _format_reminder(notification: Notification) -> str:
    return f"⏰ <b>{_escape(notification.title)}</b>\n\n{_escape(notification.body or '')}"


def _format_urgent(event: Event, score: float, draft: Post | None) -> str:
    title = _escape(event.title_local or event.title)
    parts = [f"🔴 <b>{title}</b>", f"Fırsat {score:.0f}/100"]
    if event.summary:
        parts.append(_escape(event.summary[:400]))
    if draft is not None:
        parts.append(f"<b>Hazır tweet:</b>\n<pre>{_escape(draft.text)}</pre>")
    else:
        # Say so rather than letting a missing draft look like a formatting bug.
        parts.append("<i>Taslak üretilemedi — ODIN'de açıp elle yazman gerekiyor.</i>")
    return "\n\n".join(parts)


async def push_digest(
    session: AsyncSession,
    telegram: TelegramClient,
    *,
    llm: LLMProvider | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> PushStats:
    """Everything that didn't earn an interruption, once a day, in one message.

    Leads with the day's best opportunity and a finished tweet. Without this, a quiet
    stretch where nothing clears URGENT_FLOOR would send you a list of headlines and
    no way to act on any of them — which is how a digest becomes something you stop
    opening.
    """
    stats = PushStats()
    if not telegram.configured:
        return stats
    now = now or datetime.now(UTC)

    if not force and local_hour(now) != DIGEST_HOUR:
        stats.skipped_reason = "not_digest_hour"
        return stats

    pending = [n for n in await _pending(session, now) if n.type != REMINDER]
    if not pending:
        return stats

    # Already sent one today? The cron fires several times within the digest hour.
    tz = _tz()
    midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    already = (
        await session.execute(
            select(Notification.id)
            .where(
                Notification.pushed_at.is_not(None),
                Notification.pushed_at >= midnight.astimezone(UTC),
                Notification.type != HIGH_OPPORTUNITY,
                Notification.type != REMINDER,
            )
            .limit(1)
        )
    ).first()
    if already is not None and not force:
        stats.skipped_reason = "already_digested"
        return stats

    shown = pending[:DIGEST_MAX_LINES]
    lines = [
        f"{SEVERITY_ICON.get(n.severity, '🔵')} {_escape(n.title)}" for n in shown
    ]
    body = "\n".join(lines)
    if len(pending) > len(shown):
        # Never let a cap read as "that was everything".
        body += f"\n\n<i>+{len(pending) - len(shown)} tane daha</i>"

    base = get_settings().public_base_url.rstrip("/")
    buttons: list[tuple[str, str]] = []
    header = f"📋 <b>Günün özeti</b> — {len(pending)} kayıt"

    # The best of what's waiting, with the tweet already written.
    best = await _best_event(session, pending)
    if best is not None:
        draft = await _draft_for(session, best, llm)
        header = (
            f"📋 <b>Günün özeti</b>\n\n"
            f"<b>En iyisi:</b> {_escape(best.title_local or best.title)} "
            f"({best.opportunity_score:.0f}/100)"
        )
        if draft is not None:
            header += f"\n<pre>{_escape(draft.text)}</pre>"
            buttons.append(("𝕏 Paylaş", intent_url(draft.text)))
        buttons.append(("Olayı aç", f"{base}/events/{best.id}"))
        header += f"\n\n<b>Diğerleri</b> ({len(pending)})"

    buttons.append(("ODIN'i aç", base))
    result = await telegram.send(f"{header}\n\n{body}", buttons=buttons)
    if result.ok:
        for n in pending:
            n.pushed_at = now
        stats.digested = len(pending)
    else:
        stats.errors.append(result.error or "unknown")

    await session.flush()
    return stats
