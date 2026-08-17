"""Hacker News source adapter (Algolia API). Proves SourceAdapter generalizes beyond RSS."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
ITEM_URL = "https://news.ycombinator.com/item?id={id}"


class HackerNewsAdapter(SourceAdapter):
    source_type = "hackernews"

    def __init__(
        self,
        *,
        tag: str = "front_page",
        hits: int = 50,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.tag = tag
        self.hits = hits
        self.timeout = timeout
        self._client = client

    async def _get(self) -> httpx.Response:
        params = {"tags": self.tag, "hitsPerPage": str(self.hits)}
        headers = {"User-Agent": "ODIN/0.1 (+https://odin.iamcanturk.dev)"}
        if self._client is not None:
            return await self._client.get(
                ALGOLIA_URL, params=params, headers=headers, timeout=self.timeout
            )
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(
                ALGOLIA_URL, params=params, headers=headers, timeout=self.timeout
            )

    async def fetch(
        self, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        try:
            resp = await self._get()
        except httpx.HTTPError as exc:
            return FetchResult(status="error", error=str(exc))

        if resp.status_code >= 400:
            return FetchResult(status="error", error=f"HTTP {resp.status_code}")

        hits = resp.json().get("hits", [])
        items = dedupe(self.normalize(h) for h in hits)
        return FetchResult(items=items)

    def normalize(self, raw: object) -> NormalizedItem:
        hit: dict[str, Any] = dict(raw) if not isinstance(raw, dict) else raw

        object_id = str(hit.get("objectID", ""))
        url = hit.get("url") or ITEM_URL.format(id=object_id)

        published_at: datetime | None = None
        if hit.get("created_at_i"):
            published_at = datetime.fromtimestamp(int(hit["created_at_i"]), tz=UTC)

        return NormalizedItem(
            source_item_id=object_id or None,
            url=url,
            title=hit.get("title") or hit.get("story_title"),
            text=hit.get("story_text") or hit.get("comment_text"),
            author=hit.get("author"),
            published_at=published_at,
            language=None,
            engagement={
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
            },
            metadata={"hn_url": ITEM_URL.format(id=object_id)},
            content_hash=compute_content_hash(self.source_type, object_id or url),
        )

    async def health_check(self) -> bool:
        result = await self.fetch()
        return result.status == "ok" and bool(result.items)
