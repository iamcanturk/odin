"""X Pulse: what is spiking on X right now, from tweets seen while browsing.

Complements the event console, which tracks NEWS across RSS/HN/GitHub/Reddit. This is the
X-native signal — and the discovery layer for replying, since a reply to an already-
accelerating post borrows its distribution.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import ObservedTweet, ProfileSnapshot, Topic
from app.pipeline.velocity import compute_velocity

router = APIRouter(prefix="/pulse", tags=["pulse"])

# Below this a tweet has no measurable traction, so its views/hour is noise.
MIN_VIEWS = 500


async def _own_handles(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(ProfileSnapshot.handle).distinct())
    return {h.lower() for (h,) in rows if h}


async def _topic_keywords(session: AsyncSession) -> set[str]:
    rows = await session.execute(select(Topic.keywords, Topic.name).where(Topic.enabled.is_(True)))
    words: set[str] = set()
    for keywords, name in rows:
        words.update(k.lower() for k in (keywords or []) if len(k) >= 3)
        if name and len(name) >= 3:
            words.add(name.lower())
    return words


def _matches_topics(text: str, words: set[str]) -> bool:
    low = (text or "").lower()
    return any(w in low for w in words)


class PulseTweet(BaseModel):
    external_id: str
    author_handle: str | None
    text: str
    url: str | None
    likes: int | None
    reposts: int | None
    replies: int | None
    bookmarks: int | None
    impressions: int | None
    posted_at: datetime | None
    views_per_hour: float
    score: float
    tier: str
    age_hours: float


class PulseSummary(BaseModel):
    observed: int
    window_hours: int
    items: list[PulseTweet]


@router.get("", response_model=PulseSummary)
async def get_pulse(
    session: AsyncSession = Depends(get_session),
    window_hours: int = Query(24, ge=1, le=168),
    limit: int = Query(25, ge=1, le=100),
    min_tier: str = Query("cold", pattern="^(cold|warm|hot)$"),
    min_views: int = Query(MIN_VIEWS, ge=0),
    relevant_only: bool = Query(True),
) -> PulseSummary:
    """What is spiking on X, filtered down to things actually worth reacting to.

    Browsing captures everything you scroll past — your own posts, reply fragments,
    arguments, ads-adjacent noise. None of that is a reaction opportunity, so the feed is
    filtered rather than shown raw.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)

    own = await _own_handles(session)
    # Relevance is the DEFAULT, not an option. Ranking purely by views/hour surfaces
    # mass-appeal humour — a meme at 700k views/hour will always beat a Docker post at
    # 5k, which is useless for a niche account. Falls back to everything when no topics
    # are configured, so the page is never mysteriously empty.
    topic_words = await _topic_keywords(session) if relevant_only else set()

    # Only the most recent sighting of each tweet — that's its current standing.
    latest = (
        select(
            ObservedTweet.external_id.label("eid"),
            func.max(ObservedTweet.observed_at).label("seen"),
        )
        .where(
            ObservedTweet.posted_at >= cutoff,
            # Reply fragments carry no standalone meaning.
            ObservedTweet.is_reply.is_(False),
            ObservedTweet.impressions >= min_views,
        )
        .group_by(ObservedTweet.external_id)
        .subquery()
    )
    rows = list(
        (
            await session.execute(
                select(ObservedTweet).join(
                    latest,
                    (ObservedTweet.external_id == latest.c.eid)
                    & (ObservedTweet.observed_at == latest.c.seen),
                )
            )
        ).scalars()
    )

    order = {"cold": 0, "warm": 1, "hot": 2}
    floor = order[min_tier]

    scored: list[PulseTweet] = []
    for t in rows:
        # Your own posts belong on the profile page, not in "what's happening".
        if t.author_handle and t.author_handle.lower() in own:
            continue
        if topic_words and not _matches_topics(t.text, topic_words):
            continue
        v = compute_velocity(
            impressions=t.impressions,
            likes=t.likes,
            reposts=t.reposts,
            replies=t.replies,
            bookmarks=t.bookmarks,
            posted_at=t.posted_at,
            now=now,
        )
        if order[v.tier] < floor:
            continue
        scored.append(
            PulseTweet(
                external_id=t.external_id,
                author_handle=t.author_handle,
                text=t.text,
                url=t.url,
                likes=t.likes,
                reposts=t.reposts,
                replies=t.replies,
                bookmarks=t.bookmarks,
                impressions=t.impressions,
                posted_at=t.posted_at,
                views_per_hour=v.views_per_hour,
                score=v.score,
                tier=v.tier,
                age_hours=v.age_hours,
            )
        )

    scored.sort(key=lambda p: p.views_per_hour, reverse=True)
    return PulseSummary(observed=len(rows), window_hours=window_hours, items=scored[:limit])
