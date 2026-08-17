"""GitHub source adapter: recently-created popular repositories (public REST search)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

SEARCH_URL = "https://api.github.com/search/repositories"


def _iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubAdapter(SourceAdapter):
    source_type = "github"

    def __init__(
        self,
        *,
        query: str | None = None,
        days: int = 7,
        min_stars: int = 10,
        limit: int = 30,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
        now: datetime | None = None,
    ) -> None:
        self.query = query
        self.days = days
        self.min_stars = min_stars
        self.limit = limit
        self.timeout = timeout
        self._client = client
        self._now = now

    def _build_query(self) -> str:
        if self.query:
            return self.query
        since = (self._now or datetime.now(UTC)) - timedelta(days=self.days)
        return f"created:>{since.date().isoformat()} stars:>={self.min_stars}"

    async def _get(self) -> httpx.Response:
        headers = {
            "User-Agent": "ODIN/0.1 (+https://odin.iamcanturk.dev)",
            "Accept": "application/vnd.github+json",
        }
        params = {
            "q": self._build_query(),
            "sort": "stars",
            "order": "desc",
            "per_page": str(self.limit),
        }
        if self._client is not None:
            return await self._client.get(
                SEARCH_URL, params=params, headers=headers, timeout=self.timeout
            )
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(
                SEARCH_URL, params=params, headers=headers, timeout=self.timeout
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

        repos = resp.json().get("items", [])
        items = dedupe(self.normalize(r) for r in repos)
        return FetchResult(items=items)

    def normalize(self, raw: object) -> NormalizedItem:
        repo: dict[str, Any] = dict(raw) if not isinstance(raw, dict) else raw

        repo_id = str(repo.get("id", ""))
        owner = (repo.get("owner") or {}).get("login")
        return NormalizedItem(
            source_item_id=repo_id,
            url=repo.get("html_url"),
            title=repo.get("full_name") or repo.get("name"),
            text=repo.get("description") or None,
            author=owner,
            published_at=_iso_date(repo.get("created_at")),
            language=None,
            engagement={
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "watchers": repo.get("watchers_count"),
            },
            metadata={"language": repo.get("language"), "topics": repo.get("topics", [])},
            content_hash=compute_content_hash(
                self.source_type, repo_id or repo.get("html_url", "")
            ),
        )

    async def health_check(self) -> bool:
        result = await self.fetch()
        return result.status == "ok" and bool(result.items)
