"""Reddit source adapter.

Two paths, picked automatically. With REDDIT_CLIENT_ID/SECRET set it uses app-only
OAuth against oauth.reddit.com; without them it falls back to the anonymous JSON
listings on www.reddit.com.

That fallback is why the extension relay exists: Reddit serves the anonymous
endpoint a 403 from datacenter IPs (verified — the production server gets an empty
body where a residential connection gets 30KB), so on the server it only works
authenticated. The error message says so rather than leaving you to guess.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

LISTING_URL = "https://www.reddit.com/r/{subs}/{sort}.json"
# The authenticated host. Reddit serves datacenter IPs here but 403s them on
# www.reddit.com's anonymous JSON, which is why the extension relay existed.
OAUTH_LISTING_URL = "https://oauth.reddit.com/r/{subs}/{sort}"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
USER_AGENT = "ODIN/0.1 (personal intelligence engine; +https://odin.iamcanturk.dev)"
# Reddit's app-only tokens last an hour; refresh early rather than race the expiry.
TOKEN_TTL = timedelta(minutes=50)
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
        settings = get_settings()
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self._token: str | None = None
        self._token_expires: datetime | None = None

    @property
    def authenticated(self) -> bool:
        """Credentials turn the datacenter 403 into a 200. Without them we still try
        the anonymous endpoint, which works from a residential IP and via the
        extension relay."""
        return bool(self.client_id and self.client_secret)

    async def _access_token(self, client: httpx.AsyncClient) -> str | None:
        """App-only (client_credentials) token. Read-only, no user account involved."""
        now = datetime.now(UTC)
        if self._token and self._token_expires and now < self._token_expires:
            return self._token
        try:
            response = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        token = response.json().get("access_token")
        if not token:
            return None
        self._token = token
        self._token_expires = now + TOKEN_TTL
        return token

    @property
    def _url(self) -> str:
        return LISTING_URL.format(subs="+".join(self.subreddits), sort=self.sort)

    async def _fetch_with(self, client: httpx.AsyncClient) -> httpx.Response:
        # Reddit blocks generic/default user agents; a descriptive UA is required.
        headers = {"User-Agent": USER_AGENT}
        params = {"limit": str(self.limit)}
        url = self._url

        if self.authenticated and (token := await self._access_token(client)):
            headers["Authorization"] = f"bearer {token}"
            url = OAUTH_LISTING_URL.format(
                subs="+".join(self.subreddits), sort=self.sort
            )

        return await client.get(url, params=params, headers=headers, timeout=self.timeout)

    async def _get(self) -> httpx.Response:
        if self._client is not None:
            return await self._fetch_with(self._client)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await self._fetch_with(client)

    async def fetch(
        self, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        try:
            resp = await self._get()
        except httpx.HTTPError as exc:
            return FetchResult(status="error", error=str(exc))
        if resp.status_code >= 400:
            # 403 from a datacenter IP is the specific, fixable case — say which.
            hint = (
                " (set REDDIT_CLIENT_ID/SECRET; anonymous JSON is blocked from servers)"
                if resp.status_code == 403 and not self.authenticated
                else ""
            )
            return FetchResult(status="error", error=f"HTTP {resp.status_code}{hint}")

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
