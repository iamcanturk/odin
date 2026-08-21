"""Refresh your own post metrics without the browser extension.

X's syndication endpoint — the one that powers embedded tweets on other people's
websites — serves a public JSON document per tweet id, with no auth and no rate-limit
headers. Verified working from the production datacenter IP, which is where Reddit
and most scrapers get a 403.

What it actually gives you, and this is the whole honest list:

    favorite_count      -> likes
    conversation_count  -> replies

That's it. No reposts, no impressions, no bookmarks — those exist only in the logged-in
GraphQL responses the extension reads. So this does not replace the extension; it means
likes and replies keep updating on days you never open X, and the extension fills in
the rest when you do.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)

ENDPOINT = "https://cdn.syndication.twimg.com/tweet-result"
# The endpoint wants a token param; any value works, it isn't a credential.
TOKEN = "odin"
# Identify as a browser: the CDN serves an HTML error page to unknown agents.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 15.0


@dataclass
class PublicMetrics:
    external_id: str
    likes: int | None = None
    replies: int | None = None
    text: str | None = None
    # True when X served a real tweet; False for deleted, protected or unavailable.
    found: bool = False


async def fetch_public_metrics(
    external_id: str, *, client: httpx.AsyncClient | None = None
) -> PublicMetrics:
    """One tweet's public counters. Never raises — a dead tweet is data, not an error."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
    try:
        response = await client.get(
            ENDPOINT,
            params={"id": external_id, "token": TOKEN, "lang": "en"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        if response.status_code != 200:
            return PublicMetrics(external_id=external_id)
        # A deleted or protected tweet gets an HTML tombstone, not JSON.
        if "json" not in response.headers.get("content-type", ""):
            return PublicMetrics(external_id=external_id)
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("syndication.fetch_failed", tweet=external_id, error=str(exc))
        return PublicMetrics(external_id=external_id)
    finally:
        if owns_client:
            await client.aclose()

    if not isinstance(payload, dict) or payload.get("__typename") != "Tweet":
        return PublicMetrics(external_id=external_id)

    return PublicMetrics(
        external_id=external_id,
        likes=_as_int(payload.get("favorite_count")),
        replies=_as_int(payload.get("conversation_count")),
        text=payload.get("text"),
        found=True,
    )


def _as_int(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None
