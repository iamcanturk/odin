"""Pick whose style to write in, per category (PROJECT.md §22).

Some subjects have a house format. Security advisories are the clearest case: the
identifier and the score belong in the first line, the patch status near the end,
and the proof-of-concept link last. That shape is worth borrowing.

What gets borrowed is structure, never substance — style_reference_hint() already
instructs the model to match rhythm and framing while explicitly forbidding reuse
of the source's sentences or topics, and the facts block supplies the actual CVE
numbers from our own ingested sources rather than from anyone's tweets.

The mapping lives in app_settings so adding "write security posts like @x" is a
config change, not a deploy — and so no handle is hardcoded into the codebase.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting

STYLE_MAP_KEY = "style_by_category"


async def get_style_map(session: AsyncSession) -> dict[str, str]:
    """{category: handle}. Empty by default — nothing is mimicked unless asked."""
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == STYLE_MAP_KEY))
    ).scalar_one_or_none()
    if row is None:
        return {}
    mapping = row.value.get("value")
    if not isinstance(mapping, dict):
        return {}
    return {
        str(k).lower(): str(v).lstrip("@").lower()
        for k, v in mapping.items()
        if isinstance(v, str) and v.strip()
    }


async def set_style_map(session: AsyncSession, mapping: dict[str, str]) -> dict[str, str]:
    cleaned = {
        str(k).strip().lower(): str(v).strip().lstrip("@").lower()
        for k, v in mapping.items()
        if str(v).strip()
    }
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == STYLE_MAP_KEY))
    ).scalar_one_or_none()
    if row is None:
        session.add(AppSetting(key=STYLE_MAP_KEY, value={"value": cleaned}))
    else:
        row.value = {"value": cleaned}
    await session.flush()
    return cleaned


async def style_handle_for(session: AsyncSession, category: str | None) -> str:
    """The handle to emulate for this category, or "" for your own voice."""
    if not category:
        return ""
    return (await get_style_map(session)).get(category.strip().lower(), "")
