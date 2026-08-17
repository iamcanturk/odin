"""Unit tests for ingestion helpers (no DB / no network).

The full DB path (poll -> store -> embed -> cluster -> score) is covered by the
integration tests in the test-suite issue and was verified end-to-end against a
live Postgres (idempotent: a second run creates 0 new items).
"""

from __future__ import annotations

from app.models import ContentItem, Source
from app.models.enums import SourceType
from app.pipeline.ingest import _item_text, build_adapter
from app.sources.hackernews import HackerNewsAdapter
from app.sources.rss import RSSAdapter


def test_build_adapter_rss() -> None:
    src = Source(name="Ars", type=SourceType.RSS, url="https://example.com/feed")
    adapter = build_adapter(src)
    assert isinstance(adapter, RSSAdapter)
    assert adapter.url == "https://example.com/feed"


def test_build_adapter_hackernews() -> None:
    src = Source(name="HN", type=SourceType.HACKERNEWS)
    assert isinstance(build_adapter(src), HackerNewsAdapter)


def test_build_adapter_unknown_or_missing_url() -> None:
    assert build_adapter(Source(name="X", type="unknown")) is None
    # rss without url has no adapter
    assert build_adapter(Source(name="NoURL", type=SourceType.RSS, url=None)) is None


def test_item_text_joins_title_and_text() -> None:
    assert _item_text(ContentItem(title="Title", text="Body")) == "Title Body"
    assert _item_text(ContentItem(title="Only title", text=None)) == "Only title"
    assert _item_text(ContentItem(title=None, text=None)) == ""
