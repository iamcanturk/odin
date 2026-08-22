"""Tests for Telegram push throttling: quiet hours, gaps, caps, and the digest.

The behaviour these pin down came from a real day on production: 13 pings in 24
hours, including 23:00 and 04:00, for events scoring 46-49 out of 100.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.models import Event, Notification
from app.pipeline.push import (
    MIN_GAP,
    URGENT_DAILY_CAP,
    URGENT_FLOOR,
    in_quiet_hours,
    push_digest,
    push_urgent,
)
from app.providers.telegram import TelegramClient

# 12:00 Istanbul = 09:00 UTC. Comfortably outside quiet hours.
NOON = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


def _client(handler=None):
    handler = handler or (lambda r: httpx.Response(200, json={"ok": True}))
    return httpx.MockTransport(handler)


def _patch(transport):
    """Swap httpx.AsyncClient for one bound to a mock transport."""
    original = httpx.AsyncClient

    class _Patched:
        def __enter__(self):
            httpx.AsyncClient = lambda **kw: original(transport=transport, **kw)
            return self

        def __exit__(self, *a):
            httpx.AsyncClient = original

        async def __aenter__(self):
            return self.__enter__()

        async def __aexit__(self, *a):
            self.__exit__()

    return _Patched()


async def _event(db_sessionmaker, score: float) -> Event:
    async with db_sessionmaker() as session:
        event = Event(
            title=f"event scoring {score}",
            summary="bir sey oldu",
            status="active",
            trend_score=score,
            opportunity_score=score,
            confidence_score=0.8,
            first_seen_at=NOON,
            last_seen_at=NOON,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event


async def _notify(db_sessionmaker, event: Event | None, *, type_="high_opportunity", body=None):
    async with db_sessionmaker() as session:
        session.add(
            Notification(
                type=type_,
                severity="high",
                title="baslik",
                body=body,
                event_id=event.id if event else None,
            )
        )
        await session.commit()


# ---- quiet hours ----


@pytest.mark.parametrize(
    "utc_hour,quiet",
    [(20, True), (21, True), (2, True), (4, True), (5, False), (9, False), (19, False)],
)
def test_quiet_hours_are_local_and_wrap_midnight(utc_hour, quiet):
    """Istanbul is UTC+3: 20:00 UTC is 23:00 local, which is quiet."""
    assert in_quiet_hours(datetime(2026, 8, 21, utc_hour, 0, tzinfo=UTC)) is quiet


async def test_nothing_is_pushed_during_quiet_hours(db_sessionmaker):
    event = await _event(db_sessionmaker, 90.0)
    await _notify(db_sessionmaker, event)
    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(
            session, TelegramClient("t", "c"), now=datetime(2026, 8, 21, 23, 0, tzinfo=UTC)
        )
    assert stats.sent == 0
    assert stats.skipped_reason == "quiet_hours"


# ---- the absolute floor ----


async def test_a_weak_score_does_not_interrupt_you(db_sessionmaker):
    """Below the floor nothing gets through, however many are waiting. Volume above
    the floor is held down by the daily cap and the 90-minute gap, not by the floor."""
    event = await _event(db_sessionmaker, URGENT_FLOOR - 5)
    await _notify(db_sessionmaker, event)
    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(session, TelegramClient("t", "c"), now=NOON)
    assert stats.sent == 0
    assert stats.skipped_reason == "nothing_urgent"


async def test_a_high_score_does_interrupt_you(db_sessionmaker):
    event = await _event(db_sessionmaker, URGENT_FLOOR + 20)
    await _notify(db_sessionmaker, event)
    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(session, TelegramClient("t", "c"), now=NOON)
    assert stats.sent == 1


async def test_only_the_single_best_gets_through(db_sessionmaker):
    """Three qualifying events must not become three pings."""
    for score in (65.0, 92.0, 78.0):
        await _notify(db_sessionmaker, await _event(db_sessionmaker, score))
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(__import__("json").loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True})

    async with db_sessionmaker() as session, _patch(_client(handler)):
        stats = await push_urgent(session, TelegramClient("t", "c"), now=NOON)
        await session.commit()
    assert stats.sent == 1
    assert "92" in sent[0]  # the best one, not the first one


# ---- rate limits ----


async def test_a_recent_push_blocks_the_next_one(db_sessionmaker):
    event = await _event(db_sessionmaker, 90.0)
    await _notify(db_sessionmaker, event)
    async with db_sessionmaker() as session:
        recent = Notification(type="high_opportunity", severity="high", title="onceki")
        session.add(recent)
        await session.flush()
        recent.pushed_at = NOON - MIN_GAP + timedelta(minutes=5)
        await session.commit()

    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(session, TelegramClient("t", "c"), now=NOON)
    assert stats.sent == 0
    assert stats.skipped_reason == "min_gap"


async def test_the_daily_cap_stops_the_day(db_sessionmaker):
    await _notify(db_sessionmaker, await _event(db_sessionmaker, 95.0))
    async with db_sessionmaker() as session:
        for i in range(URGENT_DAILY_CAP):
            done = Notification(type="high_opportunity", severity="high", title=f"d{i}")
            session.add(done)
            await session.flush()
            done.pushed_at = NOON - timedelta(hours=4 + i)
        await session.commit()

    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(session, TelegramClient("t", "c"), now=NOON)
    assert stats.sent == 0
    assert stats.skipped_reason == "daily_cap"


# ---- reminders bypass everything ----


async def test_a_queue_reminder_fires_even_at_night(db_sessionmaker):
    """You picked that time yourself; postponing it is not ours to do."""
    await _notify(db_sessionmaker, None, type_="post_due", body="hazir tweet")
    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_urgent(
            session, TelegramClient("t", "c"), now=datetime(2026, 8, 21, 23, 30, tzinfo=UTC)
        )
    assert stats.sent == 1


# ---- digest ----


async def test_the_digest_waits_for_its_hour(db_sessionmaker):
    await _notify(db_sessionmaker, await _event(db_sessionmaker, 40.0))
    async with db_sessionmaker() as session, _patch(_client()):
        stats = await push_digest(session, TelegramClient("t", "c"), now=NOON)
    assert stats.digested == 0
    assert stats.skipped_reason == "not_digest_hour"


async def test_the_digest_sweeps_everything_in_one_message(db_sessionmaker):
    for score in (30.0, 40.0, 49.0):
        await _notify(db_sessionmaker, await _event(db_sessionmaker, score))
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(__import__("json").loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True})

    async with db_sessionmaker() as session, _patch(_client(handler)):
        stats = await push_digest(session, TelegramClient("t", "c"), now=NOON, force=True)
        await session.commit()
    assert stats.digested == 3
    assert len(sent) == 1
    # One message, leading with the best of the three so there's something to act on.
    assert "En iyisi" in sent[0]
    assert "49" in sent[0]
    assert "Diğerleri</b> (3)" in sent[0]


async def test_a_digested_notification_is_not_sent_twice(db_sessionmaker):
    await _notify(db_sessionmaker, await _event(db_sessionmaker, 40.0))
    async with db_sessionmaker() as session, _patch(_client()):
        await push_digest(session, TelegramClient("t", "c"), now=NOON, force=True)
        await session.commit()
    async with db_sessionmaker() as session, _patch(_client()):
        again = await push_digest(session, TelegramClient("t", "c"), now=NOON, force=True)
    assert again.digested == 0
