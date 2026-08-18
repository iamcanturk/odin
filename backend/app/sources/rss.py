"""RSS/Atom source adapter with conditional-GET, parsing and normalization (PROJECT.md §26)."""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
import httpx

from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str | None:
    if not value:
        return value
    text = _TAG_RE.sub(" ", value)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def _struct_to_datetime(value: struct_time | None) -> datetime | None:
    if not value:
        return None
    # feedparser emits *_parsed as UTC struct_time.
    return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)


def parse_feed(content: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Parse feed bytes into (entries, feed_language). Pure — no network."""
    parsed = feedparser.parse(content)
    language = parsed.feed.get("language") if getattr(parsed, "feed", None) else None
    entries = [dict(e) for e in parsed.entries]
    return entries, language


class RSSAdapter(SourceAdapter):
    source_type = "rss"

    def __init__(
        self,
        url: str,
        *,
        name: str | None = None,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url
        self.name = name or url
        self.timeout = timeout
        self._client = client
        self._language: str | None = None

    def _conditional_headers(
        self, etag: str | None, last_modified: str | None
    ) -> dict[str, str]:
        headers = {"User-Agent": "ODIN/0.1 (+https://odin.iamcanturk.dev)"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    async def _get(self, headers: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(self.url, headers=headers, timeout=self.timeout)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(self.url, headers=headers, timeout=self.timeout)

    async def fetch(
        self, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        try:
            resp = await self._get(self._conditional_headers(etag, last_modified))
        except httpx.HTTPError as exc:
            return FetchResult(status="error", error=str(exc))

        if resp.status_code == 304:
            return FetchResult(not_modified=True, etag=etag, last_modified=last_modified)

        if resp.status_code >= 400:
            return FetchResult(status="error", error=f"HTTP {resp.status_code}")

        entries, self._language = parse_feed(resp.content)
        items = dedupe(self.normalize(e) for e in entries)
        return FetchResult(
            items=items,
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )

    def normalize(self, raw: object) -> NormalizedItem:
        entry: dict[str, Any] = dict(raw) if not isinstance(raw, dict) else raw

        source_item_id = entry.get("id") or entry.get("guid") or entry.get("link")
        url = entry.get("link")

        text = entry.get("summary")
        if not text and entry.get("content"):
            content = entry["content"]
            if isinstance(content, list) and content:
                text = content[0].get("value")
        text = strip_html(text)

        published_at = _struct_to_datetime(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )

        key = source_item_id or url or entry.get("title") or ""
        return NormalizedItem(
            source_item_id=source_item_id,
            url=url,
            title=strip_html(entry.get("title")),
            text=text,
            author=entry.get("author"),
            published_at=published_at,
            language=self._language,
            media=_extract_images(entry),
            content_hash=compute_content_hash(self.source_type, key),
        )

    async def health_check(self) -> bool:
        result = await self.fetch()
        return result.status == "ok" and (result.not_modified or bool(result.items))


# Tracking pixels / spacers that some feeds embed.
_IMAGE_BLOCKLIST = ("pixel", "1x1", "spacer", "blank.gif", "feedburner", "doubleclick")

_IMG_SRC_RE = re.compile(r"""<img[^>]+src=["\']([^"\']+)["\']""", re.IGNORECASE)


def _html_blobs(entry: dict[str, Any]) -> list[str]:
    """The raw (un-stripped) HTML a feed carries, where images usually hide."""
    blobs: list[str] = []
    if isinstance(entry.get("summary"), str):
        blobs.append(entry["summary"])
    content = entry.get("content")
    if isinstance(content, list):
        blobs.extend(c.get("value", "") for c in content if isinstance(c, dict))
    return blobs


def _extract_images(entry: dict[str, Any]) -> list[dict[str, str]]:
    """Pull image URLs from media fields, then from <img> tags in the feed HTML."""
    urls: list[str] = []

    def add(u: object) -> None:
        if isinstance(u, str) and u.startswith("http") and u not in urls:
            urls.append(u)

    def is_image(d: dict[str, Any]) -> bool:
        kind = str(d.get("medium") or d.get("type") or "")
        u = str(d.get("url") or d.get("href") or "").lower()
        return kind.startswith("image") or u.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))

    for m in entry.get("media_content") or []:
        if isinstance(m, dict) and is_image(m):
            add(m.get("url"))
    for m in entry.get("media_thumbnail") or []:
        if isinstance(m, dict):
            add(m.get("url"))
    for enc in entry.get("enclosures") or []:
        if isinstance(enc, dict) and is_image(enc):
            add(enc.get("href") or enc.get("url"))
    for link in entry.get("links") or []:
        if isinstance(link, dict) and link.get("rel") == "enclosure" and is_image(link):
            add(link.get("href"))
    # Fallback: most feeds ship the article image as an <img> inside the description HTML.
    if not urls:
        for blob in _html_blobs(entry):
            for src in _IMG_SRC_RE.findall(blob):
                add(src)
    # Drop tracking pixels and other 1x1 junk.
    urls = [u for u in urls if not any(bad in u.lower() for bad in _IMAGE_BLOCKLIST)]
    return [{"type": "image", "url": u} for u in urls[:3]]
