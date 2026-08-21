"""Tests for the CISA KEV adapter (actively-exploited CVEs)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.sources.cisa_kev import CISAKevAdapter


def _catalog(entries: list[dict]) -> bytes:
    return json.dumps({"title": "KEV", "vulnerabilities": entries}).encode()


def _entry(cve: str, *, days_ago: int, ransomware: str = "Unknown") -> dict:
    added = (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {
        "cveID": cve,
        "vendorProject": "Acme",
        "product": "Gateway",
        "vulnerabilityName": "Remote Code Execution",
        "dateAdded": added,
        "shortDescription": "Acme Gateway allows unauthenticated RCE.",
        "requiredAction": "Apply updates.",
        "dueDate": "2026-09-01",
        "knownRansomwareCampaignUse": ransomware,
        "cwes": ["CWE-94"],
    }


def _client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, content=body))
    )


@pytest.mark.asyncio
async def test_only_recently_added_entries_are_ingested() -> None:
    """The catalogue is cumulative (~1700 rows); the first poll must not dump history."""
    body = _catalog([_entry("CVE-2026-1", days_ago=2), _entry("CVE-2020-9", days_ago=900)])
    async with _client(body) as c:
        result = await CISAKevAdapter(recent_days=14, client=c).fetch()

    assert result.status == "ok"
    assert [i.metadata["cve"] for i in result.items] == ["CVE-2026-1"]


@pytest.mark.asyncio
async def test_normalisation_carries_what_makes_a_cve_postable() -> None:
    async with _client(_catalog([_entry("CVE-2026-2", days_ago=1)])) as c:
        item = (await CISAKevAdapter(client=c).fetch()).items[0]

    assert item.title.startswith("CVE-2026-2: Remote Code Execution")
    assert "Acme Gateway" in item.title
    assert "unauthenticated RCE" in item.text
    assert "Apply updates" in item.text
    assert item.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-2"
    assert item.metadata["cwes"] == ["CWE-94"]


@pytest.mark.asyncio
async def test_ransomware_use_is_called_out() -> None:
    """It's the single most newsworthy attribute an exploited CVE can have."""
    async with _client(_catalog([_entry("CVE-2026-3", days_ago=1, ransomware="Known")])) as c:
        item = (await CISAKevAdapter(client=c).fetch()).items[0]
    assert "ransomware" in item.text.lower()


@pytest.mark.asyncio
async def test_errors_are_reported_not_raised() -> None:
    async with _client(b"", status=403) as c:
        assert (await CISAKevAdapter(client=c).fetch()).status == "error"
    async with _client(b"not json") as c:
        result = await CISAKevAdapter(client=c).fetch()
    assert result.status == "error" and "JSON" in result.error
