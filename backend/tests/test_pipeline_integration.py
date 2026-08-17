"""End-to-end pipeline tests: pure chain (no DB) + isolated DB ingestion."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import ContentItem, Event, Source, Topic
from app.models.enums import SourceType
from app.pipeline.clustering import ClusterItem, cluster_items
from app.pipeline.content import create_candidates
from app.pipeline.ingest import run_ingestion
from app.pipeline.text import keywords
from app.pipeline.trend import Mention, compute_trend
from app.providers.base import LLMProvider
from app.providers.embedding import HashEmbeddingProvider
from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash
from app.sources.rss import parse_feed

SAME_EVENT_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><language>en</language>
  <item><title>OpenAI launches GPT-X model</title><link>https://a.com/1</link>
    <guid>a1</guid><pubDate>Wed, 02 Oct 2024 13:00:00 GMT</pubDate>
    <description>OpenAI announced the GPT-X model today</description></item>
</channel></rss>"""


def test_pure_chain_parse_cluster_score() -> None:
    """RSS bytes -> normalize -> cluster -> trend score, no DB."""
    entries, _lang = parse_feed(SAME_EVENT_RSS)
    now = datetime.now(UTC)
    items = [
        ClusterItem(
            id=str(i),
            title=e.get("title"),
            keywords=keywords(f"{e.get('title')} {e.get('summary')}"),
            url=e.get("link"),
            timestamp=now,
        )
        for i, e in enumerate(entries)
    ]
    clusters = cluster_items(items)
    assert len(clusters) == 1

    mentions = [Mention(timestamp=now, source_type="rss", source_name="A") for _ in items]
    result = compute_trend(mentions, now=now)
    assert 0.0 <= result.trend_score <= 100.0
    assert result.scoring_version == "trend-v1"


class _StubAdapter(SourceAdapter):
    """Adapter returning canned items — no network."""

    source_type = "rss"

    def __init__(self, items: list[NormalizedItem]) -> None:
        self._items = items

    async def fetch(self, *, etag=None, last_modified=None) -> FetchResult:
        return FetchResult(items=self._items)

    def normalize(self, raw: object) -> NormalizedItem:  # pragma: no cover - unused
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


def _norm(title: str, url: str, key: str) -> NormalizedItem:
    return NormalizedItem(
        source_item_id=key, url=url, title=title, text=title,
        content_hash=compute_content_hash("rss", key),
    )


async def test_ingestion_merges_same_url_and_is_idempotent(db_sessionmaker, monkeypatch) -> None:
    # Two different sources describing the same story (identical canonical URL).
    shared_url = "https://news.example.com/openai-gpt-x"
    stub_by_source = {
        "SourceA": _StubAdapter([_norm("OpenAI launches GPT-X", shared_url, "a1")]),
        "SourceB": _StubAdapter([_norm("OpenAI GPT-X: first thoughts", shared_url, "b1")]),
    }
    monkeypatch.setattr(
        "app.pipeline.ingest.build_adapter", lambda source: stub_by_source[source.name]
    )
    embedder = HashEmbeddingProvider(dim=384)

    async with db_sessionmaker() as session:
        session.add_all(
            [
                Source(name="SourceA", type=SourceType.RSS, url="https://a.example.com/feed"),
                Source(name="SourceB", type=SourceType.RSS, url="https://b.example.com/feed"),
            ]
        )
        await session.commit()

        first = await run_ingestion(session, embedder)
        assert first.items_created == 2
        # Same canonical URL -> the two items collapse into ONE event.
        assert first.events_created == 1

        item_count = await session.scalar(select(func.count(ContentItem.id)))
        event_count = await session.scalar(select(func.count(Event.id)))
        assert item_count == 2
        assert event_count == 1

        event = (await session.execute(select(Event))).scalar_one()
        assert event.trend_score >= 0.0
        assert event.scoring_version == "trend-v1"

        # Re-running against the same sources ingests nothing new (dedup on content_hash).
        second = await run_ingestion(session, embedder)
        assert second.items_created == 0
        assert second.events_created == 0
        assert await session.scalar(select(func.count(ContentItem.id))) == 2


class _JSONLLM(LLMProvider):
    """Returns valid enrichment JSON and distinct-enough post text."""

    async def generate(self, prompt, *, system=None, temperature=0.7, max_tokens=512) -> str:
        if "STRICT JSON" in (system or ""):
            return '{"summary": "OpenAI shipped a new model.", "entities": ["OpenAI"]}'
        line = next((ln for ln in prompt.splitlines() if ln.startswith("Task:")), "post")
        return f"draft :: {line}"


async def test_m1_personalization_and_content(db_sessionmaker, monkeypatch) -> None:
    stub = _StubAdapter([_norm("OpenAI launches GPT-X model", "https://x.com/gpt", "g1")])
    monkeypatch.setattr("app.pipeline.ingest.build_adapter", lambda source: stub)
    embedder = HashEmbeddingProvider(dim=384)

    async with db_sessionmaker() as session:
        session.add(
            Topic(name="AI", keywords=["openai", "gpt"], exclude_keywords=["crypto"])
        )
        session.add(Source(name="SourceA", type=SourceType.RSS, url="https://a/feed"))
        await session.commit()

        await run_ingestion(session, embedder, llm=_JSONLLM())

        event = (await session.execute(select(Event))).scalar_one()
        # Topic matched via the 'openai'/'gpt' include keywords -> personal relevance > 0.
        assert event.personal_relevance > 0
        # Opportunity computed and bounded.
        assert 0.0 <= event.opportunity_score <= 100.0

        # Content generation produces the full set of distinct ranked angles.
        candidates = await create_candidates(session, event, _JSONLLM())
        assert len(candidates) == 5
        assert {c.rank for c in candidates} == {1, 2, 3, 4, 5}
