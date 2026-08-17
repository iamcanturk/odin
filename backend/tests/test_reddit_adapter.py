"""Tests for the Reddit adapter: normalization, dedup, subreddit parsing."""

from __future__ import annotations

import json

import httpx
import pytest

from app.sources.base import compute_content_hash
from app.sources.reddit import RedditAdapter, parse_subreddits

SAMPLE = {
    "data": {
        "children": [
            {
                "data": {
                    "name": "t3_aaa",
                    "id": "aaa",
                    "title": "Rust 2.0 released",
                    "url": "https://blog.rust-lang.org/2.0",
                    "author": "rustacean",
                    "created_utc": 1727874000,
                    "score": 1200,
                    "num_comments": 340,
                    "subreddit": "programming",
                    "permalink": "/r/programming/comments/aaa/rust_20/",
                }
            },
            {"data": {"name": "t3_aaa", "id": "aaa", "title": "dup"}},  # duplicate
            {
                "data": {
                    "name": "t3_bbb",
                    "id": "bbb",
                    "title": "Ask: best editor?",
                    "url": None,
                    "permalink": "/r/programming/comments/bbb/ask/",
                    "selftext": "which one",
                }
            },
        ]
    }
}


def test_parse_subreddits() -> None:
    assert parse_subreddits("programming+technology") == ["programming", "technology"]
    assert parse_subreddits("a, b") == ["a", "b"]
    assert parse_subreddits(None) == ["all"]


def test_normalize_link_and_engagement() -> None:
    adapter = RedditAdapter(["programming"])
    item = adapter.normalize(SAMPLE["data"]["children"][0]["data"])
    assert item.title == "Rust 2.0 released"
    assert item.url == "https://blog.rust-lang.org/2.0"
    assert item.engagement["score"] == 1200
    assert item.metadata["subreddit"] == "programming"
    assert item.published_at is not None
    assert item.content_hash == compute_content_hash("reddit", "t3_aaa")


def test_normalize_selfpost_uses_permalink() -> None:
    adapter = RedditAdapter(["programming"])
    item = adapter.normalize(SAMPLE["data"]["children"][2]["data"])
    assert item.url == "https://www.reddit.com/r/programming/comments/bbb/ask/"
    assert item.text == "which one"


@pytest.mark.asyncio
async def test_fetch_dedupes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "programming" in str(request.url)
        return httpx.Response(200, content=json.dumps(SAMPLE))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RedditAdapter(["programming"], client=client)
    result = await adapter.fetch()
    await client.aclose()

    assert result.status == "ok"
    assert len(result.items) == 2  # duplicate t3_aaa collapsed
