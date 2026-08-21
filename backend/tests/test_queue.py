"""Tests for the draft reminder queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Post, PostMetric
from app.pipeline.queue import REMINDER_GRACE, due_reminders, schedule, suggest_slot

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


async def _draft(db_sessionmaker, **kw) -> Post:
    async with db_sessionmaker() as session:
        post = Post(platform="x", text="a draft", status="draft", origin="generated", **kw)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post


async def test_no_timing_evidence_means_no_suggested_slot(db_sessionmaker):
    """We'd rather say 'I don't know' than invent an hour."""
    async with db_sessionmaker() as session:
        slot = await suggest_slot(session, now=NOW)
    assert slot.when is None
    assert "veri yok" in slot.reason


async def test_slot_is_the_next_occurrence_of_the_best_hour(db_sessionmaker):
    """Seed enough posts at 14:00 that the hour clears MIN_POSTS_PER_BUCKET."""
    async with db_sessionmaker() as session:
        for i in range(6):
            post = Post(
                platform="x", text=f"p{i}", status="posted", origin="imported",
                hour=14, day_of_week=1,
            )
            session.add(post)
            await session.flush()
            session.add(PostMetric(post_id=post.id, likes=10, captured_at=NOW))
        await session.commit()

    async with db_sessionmaker() as session:
        slot = await suggest_slot(session, now=NOW)
    assert slot.hour == 14
    assert slot.when == NOW.replace(hour=14)


async def test_a_slot_already_past_today_rolls_to_tomorrow(db_sessionmaker):
    async with db_sessionmaker() as session:
        for i in range(6):
            post = Post(
                platform="x", text=f"p{i}", status="posted", origin="imported", hour=7
            )
            session.add(post)
            await session.flush()
            session.add(PostMetric(post_id=post.id, likes=10, captured_at=NOW))
        await session.commit()

    async with db_sessionmaker() as session:
        slot = await suggest_slot(session, now=NOW)  # 09:00 — 07:00 has passed
    assert slot.when == (NOW + timedelta(days=1)).replace(hour=7)


async def test_a_due_draft_produces_exactly_one_reminder(db_sessionmaker):
    post = await _draft(db_sessionmaker, scheduled_for=NOW - timedelta(minutes=5))
    async with db_sessionmaker() as session:
        first = await due_reminders(session, now=NOW)
        await session.commit()
    assert len(first) == 1

    async with db_sessionmaker() as session:
        second = await due_reminders(session, now=NOW + timedelta(minutes=10))
        await session.commit()
    assert second == []
    async with db_sessionmaker() as session:
        assert (await session.get(Post, post.id)).reminded_at is not None


async def test_a_future_draft_is_not_due_yet(db_sessionmaker):
    await _draft(db_sessionmaker, scheduled_for=NOW + timedelta(hours=3))
    async with db_sessionmaker() as session:
        assert await due_reminders(session, now=NOW) == []


async def test_a_long_overdue_draft_is_dropped_not_nagged(db_sessionmaker):
    """A reminder that fires a day late is noise."""
    await _draft(db_sessionmaker, scheduled_for=NOW - REMINDER_GRACE - timedelta(hours=1))
    async with db_sessionmaker() as session:
        assert await due_reminders(session, now=NOW) == []


async def test_rescheduling_clears_the_old_reminder(db_sessionmaker):
    post = await _draft(db_sessionmaker, scheduled_for=NOW - timedelta(minutes=5))
    async with db_sessionmaker() as session:
        await due_reminders(session, now=NOW)
        await session.commit()
    async with db_sessionmaker() as session:
        fresh = await session.get(Post, post.id)
        await schedule(session, fresh, NOW + timedelta(days=1))
        await session.commit()
        assert fresh.reminded_at is None
