"""Tests for the Hacker News adapter: normalization and dedup."""

from __future__ import annotations

import json

import httpx
import pytest

from app.sources.base import compute_content_hash
from app.sources.hackernews import HackerNewsAdapter

SAMPLE = {
    "hits": [
        {
            "objectID": "111",
            "title": "Show HN: ODIN",
            "url": "https://example.com/odin",
            "author": "can",
            "points": 42,
            "num_comments": 7,
            "created_at_i": 1727874000,
        },
        {
            "objectID": "111",  # duplicate
            "title": "Show HN: ODIN",
            "url": "https://example.com/odin",
        },
        {
            "objectID": "222",
            "title": "Ask HN: thoughts?",
            "url": None,  # no external link -> falls back to HN item url
            "author": "someone",
            "story_text": "body here",
            "created_at_i": 1727877600,
        },
    ]
}


def test_normalize_link_and_engagement() -> None:
    adapter = HackerNewsAdapter()
    item = adapter.normalize(SAMPLE["hits"][0])
    assert item.title == "Show HN: ODIN"
    assert item.url == "https://example.com/odin"
    assert item.engagement == {"points": 42, "num_comments": 7}
    assert item.published_at is not None
    assert item.content_hash == compute_content_hash("hackernews", "111")


def test_normalize_falls_back_to_item_url() -> None:
    adapter = HackerNewsAdapter()
    item = adapter.normalize(SAMPLE["hits"][2])
    assert item.url == "https://news.ycombinator.com/item?id=222"
    assert item.text == "body here"


@pytest.mark.asyncio
async def test_fetch_dedupes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(SAMPLE))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = HackerNewsAdapter(client=client)
    result = await adapter.fetch()
    await client.aclose()

    assert result.status == "ok"
    assert len(result.items) == 2  # duplicate objectID 111 collapsed
