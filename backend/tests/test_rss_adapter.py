"""Tests for the RSS adapter: parsing, normalization, dedup, conditional-GET."""

from __future__ import annotations

import httpx
import pytest

from app.schemas.ingest import NormalizedItem
from app.sources.base import compute_content_hash, dedupe
from app.sources.rss import RSSAdapter, parse_feed, strip_html

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <language>en</language>
  <item>
    <title>OpenAI launches new model</title>
    <link>https://example.com/a</link>
    <guid>urn:a</guid>
    <description>&lt;p&gt;Big &lt;b&gt;news&lt;/b&gt; today&lt;/p&gt;</description>
    <author>jane@example.com</author>
    <pubDate>Wed, 02 Oct 2024 13:00:00 GMT</pubDate>
  </item>
  <item>
    <title>OpenAI launches new model</title>
    <link>https://example.com/a</link>
    <guid>urn:a</guid>
    <description>duplicate of the first</description>
  </item>
  <item>
    <title>Second story</title>
    <link>https://example.com/b</link>
    <guid>urn:b</guid>
    <description>another item</description>
  </item>
</channel></rss>
"""


def test_strip_html() -> None:
    assert strip_html("<p>Big <b>news</b></p>") == "Big news"
    assert strip_html(None) is None
    assert strip_html("   ") is None


def test_parse_feed_language_and_count() -> None:
    entries, language = parse_feed(SAMPLE_RSS)
    assert language == "en"
    assert len(entries) == 3


def test_normalize_maps_fields() -> None:
    entries, _ = parse_feed(SAMPLE_RSS)
    adapter = RSSAdapter("https://example.com/feed")
    item = adapter.normalize(entries[0])
    assert isinstance(item, NormalizedItem)
    assert item.title == "OpenAI launches new model"
    assert item.url == "https://example.com/a"
    assert item.text == "Big news today"  # HTML stripped
    assert item.published_at is not None
    assert item.published_at.year == 2024
    assert item.content_hash == compute_content_hash("rss", "urn:a")


def test_dedupe_collapses_same_hash() -> None:
    entries, _ = parse_feed(SAMPLE_RSS)
    adapter = RSSAdapter("https://example.com/feed")
    items = dedupe(adapter.normalize(e) for e in entries)
    hashes = {i.content_hash for i in items}
    assert len(items) == 2  # urn:a duplicate collapsed, urn:b kept
    assert len(hashes) == 2


@pytest.mark.asyncio
async def test_fetch_returns_items_and_captures_etag() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_RSS, headers={"ETag": '"v1"'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RSSAdapter("https://example.com/feed", client=client)
    result = await adapter.fetch()
    await client.aclose()

    assert result.status == "ok"
    assert result.not_modified is False
    assert result.etag == '"v1"'
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_fetch_honors_conditional_get() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=SAMPLE_RSS, headers={"ETag": '"v1"'})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RSSAdapter("https://example.com/feed", client=client)
    result = await adapter.fetch(etag='"v1"')
    await client.aclose()

    assert result.not_modified is True
    assert result.etag == '"v1"'
    assert result.items == []
    assert seen_headers.get("if-none-match") == '"v1"'
