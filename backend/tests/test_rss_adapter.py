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


MEDIA_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
  <title>Media Feed</title>
  <item>
    <title>Story with a photo</title>
    <link>https://example.com/p</link>
    <guid>urn:p</guid>
    <description>has an image</description>
    <media:content url="https://cdn.example.com/photo.jpg" medium="image"/>
    <enclosure url="https://cdn.example.com/alt.png" type="image/png"/>
  </item>
  <item>
    <title>Story without a photo</title>
    <link>https://example.com/q</link>
    <guid>urn:q</guid>
    <description>no image here</description>
  </item>
</channel></rss>
"""


HTML_IMG_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Blog Feed</title>
  <item>
    <title>Article with an inline image</title>
    <link>https://example.com/x</link>
    <guid>urn:x</guid>
    <description>&lt;p&gt;&lt;img src="https://cdn.example.com/hero.jpg"/&gt;
      Body text&lt;/p&gt;</description>
  </item>
  <item>
    <title>Article with only a tracking pixel</title>
    <link>https://example.com/y</link>
    <guid>urn:y</guid>
    <description>&lt;img src="https://feeds.example.com/~r/pixel.gif"/&gt;text</description>
  </item>
</channel></rss>
"""


def test_normalize_falls_back_to_inline_img_tags() -> None:
    # Most feeds ship the article image inside the description HTML, not media:content.
    entries, _ = parse_feed(HTML_IMG_RSS)
    adapter = RSSAdapter("https://example.com/feed")
    item = adapter.normalize(entries[0])
    assert [m["url"] for m in item.media] == ["https://cdn.example.com/hero.jpg"]
    # ...and the text is still stripped of HTML.
    assert item.text and "<img" not in item.text


def test_normalize_skips_tracking_pixels() -> None:
    entries, _ = parse_feed(HTML_IMG_RSS)
    adapter = RSSAdapter("https://example.com/feed")
    assert adapter.normalize(entries[1]).media == []


def test_normalize_extracts_source_images() -> None:
    entries, _ = parse_feed(MEDIA_RSS)
    adapter = RSSAdapter("https://example.com/feed")
    with_photo = adapter.normalize(entries[0])
    urls = [m["url"] for m in with_photo.media]
    assert "https://cdn.example.com/photo.jpg" in urls
    assert all(m["type"] == "image" for m in with_photo.media)

    without = adapter.normalize(entries[1])
    assert without.media == []


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


VIDEO_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
  <title>Clips</title>
  <item>
    <title>A clip</title>
    <link>https://example.com/v</link>
    <guid>urn:v</guid>
    <enclosure url="https://cdn.example.com/clip.mp4" type="video/mp4"/>
    <description>A short clip about compilers.</description>
  </item>
</channel></rss>
"""


def test_normalize_extracts_video_and_embeds() -> None:
    entries, _ = parse_feed(VIDEO_RSS)
    item = RSSAdapter("https://example.com/feed").normalize(entries[0])
    kinds = {m["type"] for m in item.media}
    urls = {m["url"] for m in item.media}
    assert "video" in kinds
    assert "https://cdn.example.com/clip.mp4" in urls
