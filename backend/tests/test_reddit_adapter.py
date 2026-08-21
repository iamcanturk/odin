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

# ---- app-only OAuth path ----


async def test_without_credentials_it_uses_the_anonymous_endpoint(monkeypatch):
    """No credentials configured: behaviour is unchanged from before."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "reddit_client_id", "")
    monkeypatch.setattr(settings, "reddit_client_secret", "")

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": {"children": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RedditAdapter(["programming"], client=client)
        assert adapter.authenticated is False
        await adapter.fetch()

    assert "www.reddit.com" in seen[0]
    assert "oauth.reddit.com" not in seen[0]


async def test_credentials_switch_it_to_the_oauth_host(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "reddit_client_id", "id")
    monkeypatch.setattr(settings, "reddit_client_secret", "secret")

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "access_token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"data": {"children": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RedditAdapter(["programming"], client=client)
        assert adapter.authenticated is True
        await adapter.fetch()

    listing = seen[-1]
    assert "oauth.reddit.com" in str(listing.url)
    assert listing.headers["Authorization"] == "bearer tok"


async def test_the_token_is_reused_across_fetches(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "reddit_client_id", "id")
    monkeypatch.setattr(settings, "reddit_client_secret", "secret")

    tokens = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tokens
        if "access_token" in str(request.url):
            tokens += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"data": {"children": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RedditAdapter(["programming"], client=client)
        await adapter.fetch()
        await adapter.fetch()

    assert tokens == 1


async def test_a_datacenter_403_explains_the_fix(monkeypatch):
    """The most common failure should name its own remedy."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "reddit_client_id", "")
    monkeypatch.setattr(settings, "reddit_client_secret", "")

    transport = httpx.MockTransport(lambda r: httpx.Response(403, text="blocked"))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await RedditAdapter(["programming"], client=client).fetch()

    assert result.status == "error"
    assert "REDDIT_CLIENT_ID" in result.error
