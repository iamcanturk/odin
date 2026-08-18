"""Ordered adversarial critique of a draft before it ships.

The ORDER is the point: value first, polish last. There's no sense tightening the prose of
a post that shouldn't exist, so a draft that fails an early pass is reported as such and
the chain stops rather than burning tokens refining it.

Each pass asks exactly one question and returns a verdict plus a concrete rewrite, so the
user can see *why* a draft changed instead of getting an opaque "improved" version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ObservedTweet, StyleProfile
from app.pipeline.content import _sanitize, _voice_hint
from app.pipeline.cost import persist_usage
from app.pipeline.xsim import simulate
from app.providers.base import LLMProvider

# (name, the single question this pass asks)
PASSES: tuple[tuple[str, str], ...] = (
    ("skeptic", "Is this just restating something obvious? Does it actually say anything?"),
    ("expert", "Would someone with deep expertise in this area disagree or wince at it?"),
    ("scroller", "Would a stranger stop scrolling for the first line?"),
    ("competitor", "How is this different from the other posts saying the same thing?"),
    ("editor", "Is every sentence earning its place? Cut what isn't."),
)

# A pass that fails this early in the chain means the draft has a value problem, not a
# wording problem — keep refining and you just polish something not worth posting.
BLOCKING_PASSES = {"skeptic", "expert"}

_SYSTEM = (
    "You are reviewing a draft X post as a specific critic. Answer ONLY as strict JSON: "
    '{"verdict": "pass" | "fail", "rationale": "<one sentence>", "rewrite": "<the improved '
    'post, or the original unchanged if it already passes>"}. '
    "Judge only your assigned question — other critics handle the rest. "
    "The rewrite must keep the author's voice, stay self-contained, and use no em dashes "
    "or en dashes (— –)."
)


@dataclass
class PassResult:
    name: str
    verdict: str  # pass | fail
    rationale: str
    text: str  # the draft after this pass


@dataclass
class CritiqueResult:
    original: str
    final: str
    stopped_at: str | None = None  # set when a blocking pass failed
    xsim_before: float = 0.0
    xsim_after: float = 0.0
    passes: list[PassResult] = field(default_factory=list)


def _parse(raw: str, fallback: str) -> tuple[str, str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return "pass", "", fallback
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return "pass", "", fallback
    verdict = data.get("verdict") if data.get("verdict") in ("pass", "fail") else "pass"
    rewrite = data.get("rewrite")
    return (
        verdict,
        str(data.get("rationale") or ""),
        _sanitize(rewrite) if isinstance(rewrite, str) and rewrite.strip() else fallback,
    )


async def _neighbours(session: AsyncSession, limit: int = 5) -> str:
    """Recent observed tweets, so the Competitor pass compares against real posts."""
    rows = list(
        (
            await session.execute(
                select(ObservedTweet.text)
                .order_by(ObservedTweet.observed_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return "\n".join(f"- {t[:200]}" for t in rows if t)


async def critique(
    session: AsyncSession,
    text: str,
    llm: LLMProvider,
    *,
    language: str = "en",
) -> CritiqueResult:
    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == "default"))
    ).scalar_one_or_none()
    voice = _voice_hint(profile)
    lang_name = {"en": "English", "tr": "Turkish"}.get(language, "English")
    system = f"{_SYSTEM} Write the rewrite in {lang_name}. {voice}".strip()

    result = CritiqueResult(original=text, final=text, xsim_before=simulate(text).sim_score)
    current = text

    for name, question in PASSES:
        extra = ""
        if name == "competitor":
            neighbours = await _neighbours(session)
            if neighbours:
                extra = f"\n\nOther recent posts in this space:\n{neighbours}"

        raw = await llm.generate(
            f"Critic: {name}\nQuestion: {question}\n\nDraft:\n{current}{extra}\n\nReturn the JSON.",
            system=system,
            temperature=0.4,
            max_tokens=400,
        )
        verdict, rationale, rewritten = _parse(raw, current)
        current = rewritten
        result.passes.append(
            PassResult(name=name, verdict=verdict, rationale=rationale, text=current)
        )

        if verdict == "fail" and name in BLOCKING_PASSES:
            # Value problem, not a wording problem — don't polish further.
            result.stopped_at = name
            break

    result.final = current
    result.xsim_after = simulate(current).sim_score
    await persist_usage(session, purpose="critique")
    await session.commit()
    return result
