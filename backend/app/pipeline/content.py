"""Content generation: multiple distinct strategic angles per event (PROJECT.md §20-21).

Each angle is a genuinely different strategy (not a paraphrase). Posts are written in the
user's own voice, tuned for what the X ranker rewards, then scored (incl. the xsim estimate)
and ranked. Regeneration APPENDS — old candidates are kept so nothing is lost.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ContentCandidate,
    ContentItem,
    Event,
    ProfileSnapshot,
    StyleProfile,
    StyleReference,
)
from app.pipeline.cost import persist_usage
from app.pipeline.facts import extract_facts, facts_block
from app.pipeline.style_routing import style_handle_for
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


async def bio_hint(session: AsyncSession) -> str:
    """Your own bio, as context for the generator.

    It's the one place you state who you are and what you're about, which is exactly the
    positioning a post should be consistent with.
    """
    row = (
        await session.execute(
            select(ProfileSnapshot)
            .where(ProfileSnapshot.bio.is_not(None))
            .order_by(ProfileSnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None or not (row.bio or "").strip():
        return ""
    who = row.display_name or f"@{row.handle}"
    return f"The author is {who}. Their bio: \"{row.bio.strip()}\". Stay consistent with it."


async def style_reference_hint(session: AsyncSession, handle: str, *, n: int = 6) -> str:
    """Build a 'write like @handle' instruction from their best-performing sampled tweets."""
    h = handle.lstrip("@").lower()
    rows = await session.execute(
        select(StyleReference)
        .where(StyleReference.handle == h)
        .order_by(StyleReference.likes.desc().nullslast())
        .limit(n)
    )
    samples = [r.text.strip() for r in rows.scalars() if r.text and r.text.strip()]
    if not samples:
        return ""
    joined = "\n---\n".join(s[:600] for s in samples)
    return (
        f"Emulate the WRITING STYLE of @{h}. Here are examples of their posts that performed "
        f"well:\n{joined}\n"
        "Match their structure, rhythm, tone and how they open and close a post. "
        "Do NOT copy their sentences or reuse their specific topics — only the style."
    )


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
    # Identifiers and scores the model must cite rather than approximate. Empty for
    # anything non-technical, so nothing gets invented to fill the section.
    facts = facts_block(extract_facts(event.title, summary, *item_texts[:5]))
    return (
        f"Subject: {event.title}\n"
        f"What is going on: {summary}\n"
        f"Source material:\n{context}\n\n"
        + (f"{facts}\n\n" if facts else "")
        + f"Task: {instruction}\n"
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
    # Angles are independent, so issue them concurrently rather than stacking round-trips.
    raws = await asyncio.gather(
        *(
            llm.generate(
                _prompt(event, item_texts, instruction),
                system=system,
                temperature=0.8,
                max_tokens=max_tokens,
            )
            for instruction, _, _ in selected.values()
        )
    )

    drafts: list[CandidateDraft] = []
    for (angle, (_, novelty, risk)), raw in zip(selected.items(), raws, strict=True):
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


# Reply angles are NOT the post angles. A reply enters someone else's conversation, so it
# has to earn its place there; "breaking news" makes no sense as a reply.
REPLY_ANGLES: dict[str, tuple[str, float, float]] = {
    "extend": (
        "Agree with the core point, then add one concrete thing they did not say. "
        "No flattery, no 'great post' — lead with the addition.",
        0.5,
        0.15,
    ),
    "counterexample": (
        "Politely offer a specific counterexample or edge case where this does not hold. "
        "Be concrete, not contrarian for its own sake.",
        0.8,
        0.5,
    ),
    "question": (
        "Ask one sharp, genuine question that the author would actually want to answer.",
        0.6,
        0.2,
    ),
    "experience": (
        "Share a short first-hand experience that speaks to their point. Specific detail "
        "beats generality.",
        0.65,
        0.2,
    ),
}

_REPLY_SYSTEM = (
    "You write replies on X, in the author's own voice. A reply enters someone else's "
    "conversation, so it must earn its place. Rules: "
    "(1) REFERENCE SOMETHING SPECIFIC from their post — a claim, a number, a word they "
    "used. A reply that could sit under any tweet is worthless. "
    "(2) Never open with flattery ('Great post', 'This!', 'So true', 'Katılıyorum'). "
    "(3) Say ONE thing. Do not stack multiple points or end with a generic question. "
    "(4) If you have nothing concrete to add, reply with exactly: SKIP. Saying nothing is "
    "better than posting filler. "
    "(5) Stay respectful when disagreeing; the goal is a conversation, not a dunk. "
    "(6) No em dashes or en dashes (— –), no hashtags, no emoji unless the author uses them. "
    "(7) Under 280 characters. Return ONLY the reply text, no preamble or quotes."
)


async def generate_replies(
    session: AsyncSession,
    parent_text: str,
    llm: LLMProvider,
    *,
    parent_handle: str = "",
    thread_context: str = "",
    language: str = "en",
    angles: list[str] | None = None,
) -> list[CandidateDraft]:
    """Draft replies to someone else's tweet (PROJECT.md §21).

    Replying to an already-accelerating post borrows its distribution, and xsim weights a
    reply at 5.0 against a like's 0.5 — this is the highest-leverage action ODIN can
    recommend, and it previously had no way to produce one.
    """
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    name = _LANG_NAME.get(language, "English")
    system = " ".join([_REPLY_SYSTEM, f"Write in {name}.", _voice_hint(profile)]).strip()

    selected = (
        {a: REPLY_ANGLES[a] for a in angles if a in REPLY_ANGLES} if angles else REPLY_ANGLES
    )
    if not selected:
        selected = REPLY_ANGLES

    def _prompt_for(instruction: str) -> str:
        parts = []
        if parent_handle:
            parts.append(f"You are replying to @{parent_handle.lstrip('@')}.")
        parts.append(f"Their post:\n{parent_text}")
        if thread_context:
            parts.append(f"Earlier in the thread:\n{thread_context}")
        parts.append(f"Task: {instruction}\nWrite the reply:")
        return "\n\n".join(parts)

    # The angles are independent, so run them concurrently. Sequentially this was four
    # round-trips stacked end to end, which is why drafting a reply felt slow.
    raws = await asyncio.gather(
        *(
            llm.generate(_prompt_for(instruction), system=system, temperature=0.8, max_tokens=160)
            for instruction, _, _ in selected.values()
        )
    )

    drafts: list[CandidateDraft] = []
    for (angle, (_, novelty, risk)), raw in zip(selected.items(), raws, strict=True):
        text = _sanitize(raw)
        # The model is told to answer SKIP when it has nothing concrete; honour that rather
        # than presenting filler as a suggestion.
        if not text or text.strip().upper().startswith("SKIP"):
            continue
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
    await persist_usage(session, purpose="reply")
    await session.commit()
    return drafts


# On X the first line does nearly all the work — it decides whether a post_click ever
# happens. Generating 25 hooks costs about one long post in tokens but explores the
# highest-leverage dimension far more densely than 5 whole drafts do.
HOOK_TEMPLATES = (
    "I think [CONCEPT] is the [CATEGORY] that [OUTCOME].",
    "[TECHNIQUE] separates [WINNERS] from [EVERYONE ELSE].",
    "What used to require [OLD COMPLEXITY] now [NEW SIMPLICITY].",
    "Most people get [TOPIC] wrong because [REASON].",
    "[NUMBER] things about [TOPIC] that [SURPRISE].",
)

_HOOK_SYSTEM = (
    "You write opening lines for X posts — the first line only, never the whole post. "
    "Each must be concrete and specific enough that a stranger stops scrolling, and must "
    "name the actual subject rather than teasing it vaguely. No clickbait that the post "
    "cannot pay off. Do NOT use em dashes or en dashes (— –), no hashtags, no emoji. "
    "Return ONE hook per line, no numbering, no quotes, nothing else."
)


@dataclass
class Hook:
    text: str
    xsim_score: float
    rank: int = 0


async def generate_hooks(
    session: AsyncSession,
    topic: str,
    llm: LLMProvider,
    *,
    language: str = "en",
    n: int = 20,
) -> list[Hook]:
    """Generate opening lines and rank them with xsim rather than a hand-made rubric."""
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    name = _LANG_NAME.get(language, "English")
    system = " ".join([_HOOK_SYSTEM, f"Write in {name}.", _voice_hint(profile)]).strip()
    templates = "\n".join(f"- {t}" for t in HOOK_TEMPLATES)

    raw = await llm.generate(
        f"Subject: {topic}\n\nPatterns you may draw on (adapt, do not fill in literally):\n"
        f"{templates}\n\nWrite {n} different opening lines:",
        system=system,
        temperature=0.95,
        max_tokens=900,
    )

    seen: set[str] = set()
    hooks: list[Hook] = []
    for line in raw.splitlines():
        text = _sanitize(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line))
        if len(text) < 12 or text.lower() in seen:
            continue
        seen.add(text.lower())
        # post_click and copy_link_share are what a hook actually drives.
        r = simulate(text)
        score = round(
            100 * (0.6 * r.probabilities["post_click"] / 0.06
                   + 0.4 * r.probabilities["copy_link_share"] / 0.04),
            2,
        )
        hooks.append(Hook(text=text, xsim_score=min(score, 100.0)))

    hooks.sort(key=lambda h: h.xsim_score, reverse=True)
    for i, h in enumerate(hooks, start=1):
        h.rank = i
    await persist_usage(session, purpose="hooks")
    await session.commit()
    return hooks


_REFINE_SYSTEM = (
    "You rewrite an existing X (Twitter) post according to the author's instruction. "
    "Follow the instruction exactly. Keep the post self-contained: name the subject and "
    "say what happened and why it matters, so a reader with no prior context understands "
    "it. Do NOT use em dashes or en dashes (— –), no hashtag spam, no clichés. "
    "Return ONLY the rewritten post text, with no preamble, commentary or quotes."
)


async def refine_text(
    session: AsyncSession,
    text: str,
    instruction: str,
    llm: LLMProvider,
    *,
    language: str = "en",
    length: str = "short",
    context: str = "",
) -> str:
    """Rewrite a post following the user's own instruction (e.g. 'summarise the article')."""
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    name = _LANG_NAME.get(language, "English")
    system = " ".join(
        [
            _REFINE_SYSTEM,
            f"Write in {name}.",
            LENGTHS.get(length, LENGTHS["short"]),
            _voice_hint(profile),
        ]
    ).strip()

    parts = [f"Current post:\n{text}", f"\nInstruction: {instruction}"]
    if context:
        parts.append(f"\nSource material you may draw on:\n{context}")
        if block := facts_block(extract_facts(context)):
            parts.append(f"\n{block}")
    parts.append("\nRewrite the post:")

    raw = await llm.generate(
        "\n".join(parts), system=system, temperature=0.7, max_tokens=_max_tokens(length)
    )
    result = _sanitize(raw)
    await persist_usage(session, purpose="refine")
    await session.commit()
    return result


async def expand_hook(
    session: AsyncSession,
    hook: str,
    topic: str,
    llm: LLMProvider,
    *,
    language: str = "en",
    length: str = "short",
    audience: str = "technical",
    style_handle: str = "",
    n: int = 3,
) -> list[CandidateDraft]:
    """Write the posts that a chosen hook opens.

    Generating hooks is only half the job — picking one has to lead somewhere. The hook is
    kept verbatim as the first line so what you scored is what you ship, and the body is
    written to actually pay it off.
    """
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    style = await style_reference_hint(session, style_handle) if style_handle else ""
    system = _system_for(language, length=length, voice=_voice_hint(profile), style=style)
    if audience == "general":
        system += " Write for a general audience: no jargon, explain any term you must use."

    drafts: list[CandidateDraft] = []
    chosen = list(ANGLES.items())[:n]
    for angle, (instruction, novelty, risk) in chosen:
        raw = await llm.generate(
            f"Subject: {topic}\n\n"
            f"Opening line (use it VERBATIM as the first line, do not rewrite it):\n{hook}\n\n"
            f"Task: {instruction}\n"
            "Continue from that opening and pay off what it promises. "
            "The post must stand on its own. Write the full post:",
            system=system,
            temperature=0.8,
            max_tokens=_max_tokens(length),
        )
        text = _sanitize(raw)
        xsim = simulate(text).sim_score
        drafts.append(
            CandidateDraft(
                text=text, angle=angle, platform="x",
                trend_score=0.0, personal_score=0.0, source_confidence=0.0,
                novelty_score=novelty, risk_score=risk,
                viral_score=_viral_score(xsim, 0.0, 0.0, novelty, risk),
            )
        )

    drafts.sort(key=lambda d: d.viral_score, reverse=True)
    for i, d in enumerate(drafts, start=1):
        d.rank = i
    await persist_usage(session, purpose="expand")
    await session.commit()
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
    style_handle: str = "",
    n: int = 3,
) -> list[CandidateDraft]:
    """Generate posts about ANY topic the user types — no event needed (PROJECT.md §21)."""
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    style = await style_reference_hint(session, style_handle) if style_handle else ""
    system = _system_for(
        language, length=length, voice=_voice_hint(profile), audience=audience, style=style
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
    style_handle: str = "",
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
    # An explicit choice always wins; otherwise the category decides. This is what
    # makes CVE drafts come out in the house format without anyone asking each time.
    handle = style_handle or await style_handle_for(session, event.category)
    style = await style_reference_hint(session, handle) if handle else ""
    voice = " ".join(x for x in (_voice_hint(profile), await bio_hint(session)) if x)

    drafts = await generate_candidates(
        event,
        texts,
        llm,
        platform=platform,
        language=language,
        angles=angles,
        length=length,
        voice=voice,
        style=style,
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
