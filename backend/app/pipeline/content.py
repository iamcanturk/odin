"""Content generation: multiple distinct strategic angles per event (PROJECT.md §20-21).

Each angle is a genuinely different strategy (not a paraphrase). Posts are written in the
user's own voice, tuned for what the X ranker rewards, then scored (incl. the xsim estimate)
and ranked. Regeneration APPENDS — old candidates are kept so nothing is lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentCandidate, ContentItem, Event, StyleProfile
from app.pipeline.cost import persist_usage
from app.pipeline.xsim import simulate
from app.providers.base import LLMProvider

CONTENT_VERSION = "content-v2"

# angle -> (instruction, novelty 0-1, risk 0-1)
ANGLES: dict[str, tuple[str, float, float]] = {
    "breaking": ("Report it as breaking news — crisp, factual, urgent.", 0.4, 0.2),
    "contrarian": ("Take a contrarian stance that challenges the common take.", 0.85, 0.7),
    "technical": ("Explain the key technical detail most people miss.", 0.6, 0.2),
    "educational": ("Teach the reader one useful takeaway, plainly.", 0.5, 0.1),
    "question": ("Open a genuine discussion with a sharp question.", 0.55, 0.3),
}

_SYSTEM = (
    "You write high-performing X (Twitter) posts {audience}, in the author's "
    "own voice. Rules: (1) The post MUST stand on its own — name the subject explicitly and "
    "summarise what happened and why it matters, so a reader with zero prior context fully "
    "understands it. Never write cryptic detail-dumps. (2) Optimise for the X 'For You' ranker: "
    "make it worth SHARING and REPLYING to, open with a concrete hook, and don't depend on an "
    "external link to make sense. (3) Sound human — do NOT use em dashes or en dashes (— –), no "
    "hashtag spam, no clichés ('delve', 'game-changer', 'unleash', \"in today's world\"), no "
    "emoji unless the author's voice uses them. Return ONLY the post text, no surrounding quotes."
)

AUDIENCES = {
    "technical": "for a technical audience (developers, engineers)",
    "general": "for a general, non-technical audience — explain jargon in plain words",
}

# length -> instruction appended to the system prompt.
LENGTHS = {
    "short": "Keep it under 280 characters.",
    "long": (
        "Write a longer, in-depth single post (roughly 400-700 characters) that still reads "
        "as one cohesive thought."
    ),
    "story": (
        "Write it as a short narrative: set the scene, build tension, land a payoff. "
        "Roughly 600-1000 characters, in flowing prose, first person where it fits. "
        "Tell it like a story, not a bulletin."
    ),
    "thread": (
        "Write a thread of 4-6 numbered posts. Put each post on its own line prefixed with "
        "its number (1/ 2/ 3/ ...). The first post must hook and state the subject; the last "
        "must land a takeaway. Keep each post under 280 characters."
    ),
}

_LANG_NAME = {"en": "English", "tr": "Turkish"}

# em/en dashes and other AI-tell punctuation the user doesn't want.
_DASH_RE = re.compile(r"\s*[—–]\s*")


def _system_for(
    language: str, *, length: str, voice: str, audience: str = "technical", style: str = ""
) -> str:
    name = _LANG_NAME.get(language, "English")
    base = _SYSTEM.format(audience=AUDIENCES.get(audience, AUDIENCES["technical"]))
    parts = [base, f"Write the post in {name}.", LENGTHS.get(length, LENGTHS["short"])]
    if voice:
        parts.append(voice)
    if style:
        parts.append(style)
    return " ".join(parts)


def _voice_hint(profile: StyleProfile | None) -> str:
    """A compact description of the author's voice, for the system prompt."""
    if profile is None:
        return ""
    f = profile.features or {}
    bits: list[str] = []
    if profile.summary:
        bits.append(f"Author's voice: {profile.summary}")
    terms = f.get("top_terms")
    if isinstance(terms, list) and terms:
        bits.append("They often write about: " + ", ".join(str(t) for t in terms[:8]) + ".")
    if isinstance(f.get("emoji_rate"), (int, float)) and f["emoji_rate"] < 0.05:
        bits.append("They almost never use emoji.")
    if isinstance(f.get("question_rate"), (int, float)) and f["question_rate"] > 0.25:
        bits.append("They often ask questions.")
    if bits:
        bits.append("Match this voice without copying past posts verbatim.")
    return " ".join(bits)


def _max_tokens(length: str) -> int:
    return {"short": 160, "long": 400, "story": 700, "thread": 700}.get(length, 160)


def _sanitize(text: str) -> str:
    """Strip AI-tells the user dislikes (em/en dashes) and stray wrapping quotes."""
    t = text.strip().strip('"').strip("'").strip()
    t = _DASH_RE.sub(", ", t)  # "foo — bar" / "foo–bar" -> "foo, bar"
    return t.strip()


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


def _viral_score(xsim: float, trend: float, personal: float, novelty: float, risk: float) -> float:
    # Algorithm-aware: the xsim ranker estimate carries the most weight.
    return round(
        0.35 * xsim
        + 0.25 * trend
        + 0.20 * personal
        + 0.12 * (novelty * 100)
        + 0.08 * ((1 - risk) * 100),
        2,
    )


def _prompt(event: Event, item_texts: list[str], instruction: str) -> str:
    context = "\n".join(f"- {t}" for t in item_texts[:5] if t)
    summary = event.summary or event.title
    return (
        f"Subject: {event.title}\n"
        f"What is going on: {summary}\n"
        f"Source material:\n{context}\n\n"
        f"Task: {instruction}\n"
        f"Remember: make it self-contained so anyone understands the subject. Write the post:"
    )


async def generate_candidates(
    event: Event,
    item_texts: list[str],
    llm: LLMProvider,
    *,
    platform: str = "x",
    language: str = "en",
    angles: list[str] | None = None,
    length: str = "short",
    voice: str = "",
    audience: str = "technical",
    style: str = "",
) -> list[CandidateDraft]:
    system = _system_for(language, length=length, voice=voice, audience=audience, style=style)
    # When the user picks a specific kind, generate only that angle; else all.
    selected = {a: ANGLES[a] for a in angles if a in ANGLES} if angles else ANGLES
    if not selected:
        selected = ANGLES
    max_tokens = _max_tokens(length)
    tf = min(1.0, max(0.0, event.trend_score / 100.0))
    pf = min(1.0, max(0.0, event.personal_relevance / 100.0))
    drafts: list[CandidateDraft] = []
    for angle, (instruction, novelty, risk) in selected.items():
        raw = await llm.generate(
            _prompt(event, item_texts, instruction),
            system=system,
            temperature=0.8,
            max_tokens=max_tokens,
        )
        text = _sanitize(raw)
        xsim = simulate(text, trend_fit=tf, personal_fit=pf).sim_score
        drafts.append(
            CandidateDraft(
                text=text,
                angle=angle,
                platform=platform,
                trend_score=event.trend_score,
                personal_score=event.personal_relevance,
                source_confidence=event.confidence_score,
                novelty_score=novelty,
                risk_score=risk,
                viral_score=_viral_score(
                    xsim, event.trend_score, event.personal_relevance, novelty, risk
                ),
            )
        )

    drafts.sort(key=lambda d: d.viral_score, reverse=True)
    for i, draft in enumerate(drafts, start=1):
        draft.rank = i
    return drafts


async def compose_freeform(
    session: AsyncSession,
    topic: str,
    llm: LLMProvider,
    *,
    language: str = "en",
    length: str = "short",
    audience: str = "technical",
    angles: list[str] | None = None,
    n: int = 3,
) -> list[CandidateDraft]:
    """Generate posts about ANY topic the user types — no event needed (PROJECT.md §21)."""
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    system = _system_for(
        language, length=length, voice=_voice_hint(profile), audience=audience
    )
    selected = (
        {a: ANGLES[a] for a in angles if a in ANGLES}
        if angles
        else dict(list(ANGLES.items())[:n])
    )
    if not selected:
        selected = dict(list(ANGLES.items())[:n])

    drafts: list[CandidateDraft] = []
    for angle, (instruction, novelty, risk) in selected.items():
        raw = await llm.generate(
            f"Topic: {topic}\n\nTask: {instruction}\n"
            f"Make it self-contained so anyone understands the topic. Write the post:",
            system=system,
            temperature=0.85,
            max_tokens=_max_tokens(length),
        )
        text = _sanitize(raw)
        xsim = simulate(text).sim_score
        drafts.append(
            CandidateDraft(
                text=text,
                angle=angle,
                platform="x",
                trend_score=0.0,
                personal_score=0.0,
                source_confidence=0.0,
                novelty_score=novelty,
                risk_score=risk,
                viral_score=_viral_score(xsim, 0.0, 0.0, novelty, risk),
            )
        )
    drafts.sort(key=lambda d: d.viral_score, reverse=True)
    for i, d in enumerate(drafts, start=1):
        d.rank = i
    await persist_usage(session, purpose="compose")
    await session.commit()
    return drafts


async def create_candidates(
    session: AsyncSession,
    event: Event,
    llm: LLMProvider,
    *,
    platform: str = "x",
    language: str = "en",
    angles: list[str] | None = None,
    length: str = "short",
) -> list[ContentCandidate]:
    """Generate + persist ranked candidates. Regeneration APPENDS (keeps history)."""
    rows = await session.execute(
        select(ContentItem.title, ContentItem.text)
        .where(ContentItem.event_id == event.id)
        .limit(5)
    )
    texts = [" ".join(p for p in (t, x) if p) for t, x in rows]

    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()

    drafts = await generate_candidates(
        event,
        texts,
        llm,
        platform=platform,
        language=language,
        angles=angles,
        length=length,
        voice=_voice_hint(profile),
    )

    session.add_all(
        [
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
    )
    await persist_usage(session, purpose="generate")
    await session.commit()

    # Return the full history for this event, newest batch first.
    result = await session.execute(
        select(ContentCandidate)
        .where(ContentCandidate.event_id == event.id)
        .order_by(ContentCandidate.created_at.desc(), ContentCandidate.rank)
    )
    return list(result.scalars())
