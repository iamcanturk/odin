"""Tests for the GitHub adapter: query building, normalization, dedup."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.sources.base import compute_content_hash
from app.sources.github import GitHubAdapter

SAMPLE = {
    "items": [
        {
            "id": 42,
            "full_name": "acme/rocket",
            "html_url": "https://github.com/acme/rocket",
            "description": "A fast thing",
            "owner": {"login": "acme"},
            "created_at": "2026-08-15T10:00:00Z",
            "stargazers_count": 900,
            "forks_count": 30,
            "language": "Rust",
            "topics": ["cli", "rust"],
        },
        {"id": 42, "full_name": "acme/rocket", "html_url": "https://github.com/acme/rocket"},
        {
            "id": 99,
            "full_name": "beta/tool",
            "html_url": "https://github.com/beta/tool",
            "owner": {"login": "beta"},
            "created_at": "2026-08-16T12:00:00Z",
            "stargazers_count": 120,
        },
    ]
}


def test_build_query_uses_recent_date() -> None:
    adapter = GitHubAdapter(days=7, min_stars=10, now=datetime(2026, 8, 17, tzinfo=UTC))
    q = adapter._build_query()
    assert "created:>2026-08-10" in q
    assert "stars:>=10" in q


def test_normalize_repo() -> None:
    adapter = GitHubAdapter()
    item = adapter.normalize(SAMPLE["items"][0])
    assert item.title == "acme/rocket"
    assert item.url == "https://github.com/acme/rocket"
    assert item.author == "acme"
    assert item.engagement["stars"] == 900
    assert item.metadata["language"] == "Rust"
    assert item.published_at is not None and item.published_at.year == 2026
    assert item.content_hash == compute_content_hash("github", "42")


@pytest.mark.asyncio
async def test_fetch_dedupes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "search/repositories" in str(request.url)
        return httpx.Response(200, content=json.dumps(SAMPLE))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GitHubAdapter(client=client)
    result = await adapter.fetch()
    await client.aclose()

    assert result.status == "ok"
    assert len(result.items) == 2  # duplicate id 42 collapsed
