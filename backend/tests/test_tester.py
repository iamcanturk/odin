"""Tests for the tweet tester (pure combine + DB analyze)."""

from __future__ import annotations

from app.pipeline.tester import DISCLAIMER, analyze, combine_viral
from app.providers.embedding import HashEmbeddingProvider


def test_combine_viral_weighted() -> None:
    assert combine_viral(100, 100, 100, 100) == 100.0
    assert combine_viral(0, 0, 0, 0) == 0.0
    # weighting: xsim dominates
    high_x = combine_viral(80, 0, 0, 0)
    high_novelty = combine_viral(0, 0, 0, 80)
    assert high_x > high_novelty


async def test_analyze_returns_full_breakdown(db_sessionmaker) -> None:
    embedder = HashEmbeddingProvider(dim=384)
    async with db_sessionmaker() as session:
        result = await analyze(session, "Why is nobody discussing agent infra cost?", embedder)

    assert 0.0 <= result.viral_potential <= 100.0
    assert 0.0 <= result.x_simulation <= 100.0
    assert 0.0 <= result.negative_risk <= 100.0
    assert result.disclaimer == DISCLAIMER
    assert result.strengths and result.weaknesses
    # A question should surface as a reply-inviting strength.
    assert any("repl" in s.lower() for s in result.strengths)


async def test_analyze_no_profile_uses_neutral_personal_fit(db_sessionmaker) -> None:
    embedder = HashEmbeddingProvider(dim=384)
    async with db_sessionmaker() as session:
        result = await analyze(session, "A neutral statement about databases.", embedder)
    # No style profile seeded -> neutral 50.
    assert result.personal_fit == 50.0
