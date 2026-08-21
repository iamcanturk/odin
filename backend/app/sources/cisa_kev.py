"""CISA Known Exploited Vulnerabilities (KEV) adapter.

The KEV catalogue is the highest-signal CVE source there is: it lists vulnerabilities that
are being exploited IN THE WILD right now, not the thousands published monthly that nobody
ever attacks. That distinction is exactly what makes a CVE worth posting about.

The catalogue is cumulative (~1700 entries going back years), so only recently ADDED
entries are ingested — otherwise the first poll would flood the console with history.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.schemas.ingest import FetchResult, NormalizedItem
from app.sources.base import SourceAdapter, compute_content_hash, dedupe

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# Anything older than this is history, not news.
DEFAULT_RECENT_DAYS = 14


class CISAKevAdapter(SourceAdapter):
    source_type = "cisa_kev"

    def __init__(
        self,
        *,
        url: str = KEV_URL,
        recent_days: int = DEFAULT_RECENT_DAYS,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url
        self.recent_days = recent_days
        self.timeout = timeout
        self._client = client

    async def _get(self, headers: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(self.url, headers=headers, timeout=self.timeout)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await client.get(self.url, headers=headers, timeout=self.timeout)

    async def fetch(
        self, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        headers = {"User-Agent": "ODIN/0.1 (+https://odin.iamcanturk.dev)"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        try:
            resp = await self._get(headers)
        except httpx.HTTPError as exc:
            return FetchResult(status="error", error=str(exc))

        if resp.status_code == 304:
            return FetchResult(not_modified=True, etag=etag, last_modified=last_modified)
        if resp.status_code >= 400:
            return FetchResult(status="error", error=f"HTTP {resp.status_code}")

        try:
            payload = json.loads(resp.content)
        except json.JSONDecodeError as exc:
            return FetchResult(status="error", error=f"bad JSON: {exc}")

        cutoff = datetime.now(UTC) - timedelta(days=self.recent_days)
        items = [
            self.normalize(v)
            for v in payload.get("vulnerabilities", [])
            if _added_at(v) is not None and _added_at(v) >= cutoff
        ]
        return FetchResult(
            items=dedupe(items),
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )

    def normalize(self, raw: object) -> NormalizedItem:
        v: dict[str, Any] = dict(raw) if not isinstance(raw, dict) else raw
        cve = str(v.get("cveID") or "").strip()
        vendor = " ".join(x for x in (v.get("vendorProject"), v.get("product")) if x)
        name = str(v.get("vulnerabilityName") or "").strip()

        title = f"{cve}: {name}" if name else cve
        if vendor:
            title = f"{title} ({vendor})"

        parts = [str(v.get("shortDescription") or "").strip()]
        # Ransomware use is the single most newsworthy attribute an exploited CVE has.
        if str(v.get("knownRansomwareCampaignUse") or "").lower() == "known":
            parts.append("Known to be used in ransomware campaigns.")
        if v.get("requiredAction"):
            parts.append(f"Required action: {v['requiredAction']}")
        if v.get("dueDate"):
            parts.append(f"Federal remediation due {v['dueDate']}.")

        return NormalizedItem(
            source_item_id=cve or None,
            url=f"https://nvd.nist.gov/vuln/detail/{cve}" if cve else None,
            title=title or None,
            text=" ".join(p for p in parts if p) or None,
            published_at=_added_at(v),
            language="en",
            metadata={
                "cve": cve,
                "vendor": v.get("vendorProject"),
                "product": v.get("product"),
                "ransomware": v.get("knownRansomwareCampaignUse"),
                "cwes": v.get("cwes") or [],
            },
            content_hash=compute_content_hash(self.source_type, cve or title),
        )

    async def health_check(self) -> bool:
        result = await self.fetch()
        return result.status == "ok"


def _added_at(v: dict[str, Any]) -> datetime | None:
    raw = v.get("dateAdded")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None
