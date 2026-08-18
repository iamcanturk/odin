"""Content generation: multiple distinct strategic angles per event (PROJECT.md §20-21).

Each angle is a genuinely different strategy (not a paraphrase). Candidates are scored
and ranked. The LLM writes the text; numeric scores stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentCandidate, ContentItem, Event
from app.pipeline.cost import persist_usage
from app.providers.base import LLMProvider

CONTENT_VERSION = "content-v1"

# angle -> (instruction, novelty 0-1, risk 0-1)
ANGLES: dict[str, tuple[str, float, float]] = {
    "breaking": ("Report it as breaking news — crisp, factual, urgent.", 0.4, 0.2),
    "contrarian": ("Take a contrarian stance that challenges the common take.", 0.85, 0.7),
    "technical": ("Explain the key technical detail most people miss.", 0.6, 0.2),
    "educational": ("Teach the reader one useful takeaway, plainly.", 0.5, 0.1),
    "question": ("Open a genuine discussion with a sharp question.", 0.55, 0.3),
}

_SYSTEM = (
    "You write concise, analytical social posts for a technical audience. "
    "Return ONLY the post text (no quotes, no hashtags spam, <= 280 characters)."
)

_LANG_NAME = {"en": "English", "tr": "Turkish"}


def _system_for(language: str) -> str:
    name = _LANG_NAME.get(language, "English")
    return f"{_SYSTEM} Write the post in {name}."


@dataclass
class CandidateDraft:
    text: str
    angle: str
    platform: str
    trend_score: float
    personal_score: float
    source_confidence: float
    novelty_score: float
    risk_score: float
    viral_score: float
    rank: int = 0


def _viral_score(trend: float, personal: float, novelty: float, risk: float) -> float:
    return round(
        0.35 * trend + 0.35 * personal + 0.20 * (novelty * 100) + 0.10 * ((1 - risk) * 100),
        2,
    )


def _prompt(event: Event, item_texts: list[str], instruction: str) -> str:
    context = "\n".join(f"- {t}" for t in item_texts[:5] if t)
    summary = event.summary or event.title
    return (
        f"Event: {event.title}\n"
        f"Summary: {summary}\n"
        f"Context:\n{context}\n\n"
        f"Task: {instruction}\nWrite the post:"
    )


async def generate_candidates(
    event: Event,
    item_texts: list[str],
    llm: LLMProvider,
    *,
    platform: str = "x",
    language: str = "en",
    angles: list[str] | None = None,
) -> list[CandidateDraft]:
    system = _system_for(language)
    # When the user picks a specific kind, generate only that angle; else all.
    selected = {a: ANGLES[a] for a in angles if a in ANGLES} if angles else ANGLES
    if not selected:
        selected = ANGLES
    drafts: list[CandidateDraft] = []
    for angle, (instruction, novelty, risk) in selected.items():
        text = await llm.generate(
            _prompt(event, item_texts, instruction),
            system=system,
            temperature=0.8,
            max_tokens=160,
        )
        drafts.append(
            CandidateDraft(
                text=text.strip(),
                angle=angle,
                platform=platform,
                trend_score=event.trend_score,
                personal_score=event.personal_relevance,
                source_confidence=event.confidence_score,
                novelty_score=novelty,
                risk_score=risk,
                viral_score=_viral_score(
                    event.trend_score, event.personal_relevance, novelty, risk
                ),
            )
        )

    drafts.sort(key=lambda d: d.viral_score, reverse=True)
    for i, draft in enumerate(drafts, start=1):
        draft.rank = i
    return drafts


async def create_candidates(
    session: AsyncSession,
    event: Event,
    llm: LLMProvider,
    *,
    platform: str = "x",
    language: str = "en",
    angles: list[str] | None = None,
) -> list[ContentCandidate]:
    """Regenerate + persist ranked candidates for an event."""
    rows = await session.execute(
        select(ContentItem.title, ContentItem.text)
        .where(ContentItem.event_id == event.id)
        .limit(5)
    )
    texts = [" ".join(p for p in (t, x) if p) for t, x in rows]

    drafts = await generate_candidates(
        event, texts, llm, platform=platform, language=language, angles=angles
    )

    await session.execute(
        delete(ContentCandidate).where(ContentCandidate.event_id == event.id)
    )
    candidates = [
        ContentCandidate(
            event_id=event.id,
            text=d.text,
            angle=d.angle,
            platform=d.platform,
            trend_score=d.trend_score,
            personal_score=d.personal_score,
            viral_score=d.viral_score,
            source_confidence=d.source_confidence,
            novelty_score=d.novelty_score,
            risk_score=d.risk_score,
            rank=d.rank,
            model_version=CONTENT_VERSION,
        )
        for d in drafts
    ]
    session.add_all(candidates)
    await persist_usage(session, purpose="generate")
    await session.commit()
    for c in candidates:
        await session.refresh(c)
    return candidates
