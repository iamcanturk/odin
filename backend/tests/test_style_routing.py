"""Tests for per-category style routing.

Security advisories have a house format — identifier and score up front, patch
status near the end, PoC link last. This routes generation to a stored reference
for those categories without anyone choosing it each time.
"""

from __future__ import annotations

from app.models import StyleReference
from app.pipeline.content import style_reference_hint
from app.pipeline.style_routing import get_style_map, set_style_map, style_handle_for


async def test_nothing_is_emulated_by_default(db_sessionmaker):
    """No mapping configured means your own voice — never a surprise impersonation."""
    async with db_sessionmaker() as session:
        assert await get_style_map(session) == {}
        assert await style_handle_for(session, "cve") == ""


async def test_a_category_routes_to_its_handle(db_sessionmaker):
    async with db_sessionmaker() as session:
        await set_style_map(session, {"cve": "@SomeHandle", "security": "somehandle"})
        await session.commit()
    async with db_sessionmaker() as session:
        assert await style_handle_for(session, "cve") == "somehandle"
        assert await style_handle_for(session, "CVE") == "somehandle"
        assert await style_handle_for(session, "ai") == ""


async def test_an_absent_category_is_not_an_error(db_sessionmaker):
    async with db_sessionmaker() as session:
        assert await style_handle_for(session, None) == ""
        assert await style_handle_for(session, "") == ""


async def test_blank_handles_are_dropped_not_stored(db_sessionmaker):
    async with db_sessionmaker() as session:
        cleaned = await set_style_map(session, {"cve": "  ", "security": "x"})
        await session.commit()
    assert cleaned == {"security": "x"}


async def test_the_mapping_is_replaced_not_merged(db_sessionmaker):
    async with db_sessionmaker() as session:
        await set_style_map(session, {"cve": "first"})
        await session.commit()
    async with db_sessionmaker() as session:
        await set_style_map(session, {"security": "second"})
        await session.commit()
    async with db_sessionmaker() as session:
        assert await get_style_map(session) == {"security": "second"}


async def test_the_hint_borrows_format_and_forbids_copying(db_sessionmaker):
    """The whole point is structure, not substance."""
    async with db_sessionmaker() as session:
        session.add(
            StyleReference(
                handle="somehandle",
                external_id="1",
                text="🔴 Kritik açık - CVE-2026-1 (CVSS: 10)\n\nAçıklama.\n\nPoC: link",
                likes=9,
            )
        )
        await session.commit()
    async with db_sessionmaker() as session:
        hint = await style_reference_hint(session, "somehandle")

    assert "CVSS" in hint  # the sample is shown so the shape can be learned
    assert "Do NOT copy their sentences" in hint
    assert "only the style" in hint


async def test_an_unknown_handle_yields_no_hint(db_sessionmaker):
    """A mapping pointing at a handle with no samples must degrade, not invent one."""
    async with db_sessionmaker() as session:
        assert await style_reference_hint(session, "nobody") == ""
