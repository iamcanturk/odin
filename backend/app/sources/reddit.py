"""Reddit source adapter using the public JSON listings (no OAuth)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

LISTING_URL = "https://www.reddit.com/r/{subs}/{sort}.json"
PERMALINK_BASE = "https://www.reddit.com"


def parse_subreddits(spec: str | None) -> list[str]:
    """Parse a source url/spec like 'programming+technology' or 'a,b' into subreddits."""
    if not spec:
        return ["all"]
    raw = spec.replace(",", "+")
    subs = [s.strip() for s in raw.split("+") if s.strip()]
    return subs or ["all"]


class RedditAdapter(SourceAdapter):
    source_type = "reddit"

    def __init__(
        self,
        subreddits: list[str] | None = None,
        *,
        sort: str = "hot",
        limit: int = 50,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.subreddits = subreddits or ["all"]
        self.sort = sort
        self.limit = limit
        self.timeout = timeout
        self._client = client

    @property
    def _url(self) -> str:
        return LISTING_URL.format(subs="+".join(self.subreddits), sort=self.sort)

    async def _get(self) -> httpx.Response:
        # Reddit blocks generic/default user agents; a descriptive UA is required.
        headers = {"User-Agent": "ODIN/0.1 (personal intelligence engine; +https://odin.iamcanturk.dev)"}
        params = {"limit": str(self.limit)}
        if self._client is not None:
            return await self._client.get(
                self._url, params=params, headers=headers, timeout=self.timeout
            )
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(
                self._url, params=params, headers=headers, timeout=self.timeout
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

        children = resp.json().get("data", {}).get("children", [])
        items = dedupe(self.normalize(c.get("data", {})) for c in children)
        return FetchResult(items=items)

    def normalize(self, raw: object) -> NormalizedItem:
        post: dict[str, Any] = dict(raw) if not isinstance(raw, dict) else raw

        post_id = post.get("name") or f"t3_{post.get('id', '')}"
        permalink = post.get("permalink")
        # For link posts `url` is the external link; keep the reddit thread in metadata.
        url = post.get("url") or (f"{PERMALINK_BASE}{permalink}" if permalink else None)

        published_at: datetime | None = None
        if post.get("created_utc"):
            published_at = datetime.fromtimestamp(float(post["created_utc"]), tz=UTC)

        return NormalizedItem(
            source_item_id=post_id,
            url=url,
            title=post.get("title"),
            text=post.get("selftext") or None,
            author=post.get("author"),
            published_at=published_at,
            language=None,
            engagement={
                "score": post.get("score"),
                "num_comments": post.get("num_comments"),
                "upvote_ratio": post.get("upvote_ratio"),
            },
            metadata={
                "subreddit": post.get("subreddit"),
                "permalink": f"{PERMALINK_BASE}{permalink}" if permalink else None,
            },
            content_hash=compute_content_hash(self.source_type, post_id),
        )

    async def health_check(self) -> bool:
        result = await self.fetch()
        return result.status == "ok" and bool(result.items)
