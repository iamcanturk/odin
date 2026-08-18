"""Tests for the ordered critique chain and hook variant generation."""

from __future__ import annotations

import json

from app.pipeline.content import generate_hooks
from app.pipeline.critique import BLOCKING_PASSES, PASSES, critique
from app.providers.base import LLMProvider


class _CritiqueLLM(LLMProvider):
    """Replies as each critic; fails whichever pass is named in `fail_on`."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.seen: list[str] = []

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        name = prompt.splitlines()[0].replace("Critic: ", "").strip()
        self.seen.append(name)
        verdict = "fail" if name == self.fail_on else "pass"
        return json.dumps(
            {
                "verdict": verdict,
                "rationale": f"{name} says {verdict}",
                "rewrite": f"rewritten by {name} — with a dash",
            }
        )


async def test_passes_run_in_value_first_order(db_sessionmaker) -> None:
    llm = _CritiqueLLM()
    async with db_sessionmaker() as session:
        result = await critique(session, "a draft", llm)
    assert llm.seen == [name for name, _ in PASSES]
    assert llm.seen[0] == "skeptic"  # value before polish
    assert llm.seen[-1] == "editor"
    assert len(result.passes) == len(PASSES)
    # Rewrites are sanitized like everything else.
    assert "—" not in result.final


async def test_a_failed_value_pass_stops_the_chain(db_sessionmaker) -> None:
    """No point polishing something that shouldn't ship."""
    llm = _CritiqueLLM(fail_on="skeptic")
    async with db_sessionmaker() as session:
        result = await critique(session, "an obvious restatement", llm)
    assert result.stopped_at == "skeptic"
    assert llm.seen == ["skeptic"]  # expert/scroller/... never ran
    assert len(result.passes) == 1


async def test_a_failed_late_pass_does_not_stop_the_chain(db_sessionmaker) -> None:
    llm = _CritiqueLLM(fail_on="scroller")
    async with db_sessionmaker() as session:
        result = await critique(session, "a draft", llm)
    assert "scroller" not in BLOCKING_PASSES
    assert result.stopped_at is None
    assert llm.seen == [name for name, _ in PASSES]


async def test_malformed_llm_output_leaves_the_draft_intact(db_sessionmaker) -> None:
    class _Junk(LLMProvider):
        async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
            return "not json at all"

    async with db_sessionmaker() as session:
        result = await critique(session, "the original draft", _Junk())
    assert result.final == "the original draft"


class _HookLLM(LLMProvider):
    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        return "\n".join(
            [
                "1. How to ship faster: the 3 habits that matter",
                "- Most teams get Docker caching wrong because of layer order",
                "Why 90% of CI pipelines waste half their time",
                "Why 90% of CI pipelines waste half their time",  # duplicate
                "short",  # too short, dropped
            ]
        )


async def test_hooks_are_cleaned_deduped_and_ranked(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        hooks = await generate_hooks(session, "docker", _HookLLM())

    texts = [h.text for h in hooks]
    assert len(texts) == 3  # duplicate and the too-short line are dropped
    # List markers and numbering are stripped.
    assert all(not t.startswith(("1.", "-", "*")) for t in texts)
    # Ranked best-first by the xsim-derived score.
    assert [h.rank for h in hooks] == [1, 2, 3]
    scores = [h.xsim_score for h in hooks]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
