"""LLM usage/cost tracking (PROJECT.md §44).

The provider records token usage into a task-local buffer; the pipeline/endpoint
persists it to `llm_usage` with an estimated cost after each LLM operation.
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import LlmUsage

_buffer: ContextVar[list[dict] | None] = ContextVar("odin_llm_usage", default=None)


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    s = get_settings()
    return round(
        prompt_tokens / 1_000_000 * s.llm_price_in_per_m
        + completion_tokens / 1_000_000 * s.llm_price_out_per_m,
        6,
    )


def record(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Called by the LLM provider after each call."""
    buf = _buffer.get()
    if buf is None:
        buf = []
        _buffer.set(buf)
    buf.append(
        {"model": model, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    )


async def persist_usage(session: AsyncSession, purpose: str) -> float:
    """Write buffered usage to llm_usage with cost; clear the buffer. Returns total cost."""
    buf = _buffer.get() or []
    _buffer.set([])
    total = 0.0
    for u in buf:
        cost = estimate_cost(u["prompt_tokens"], u["completion_tokens"])
        total += cost
        session.add(
            LlmUsage(
                model=u["model"],
                purpose=purpose,
                prompt_tokens=u["prompt_tokens"],
                completion_tokens=u["completion_tokens"],
                cost_usd=cost,
            )
        )
    return round(total, 6)
