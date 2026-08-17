"""SourceAdapter: the common interface every content source implements (PROJECT.md §4)."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.schemas.ingest import FetchResult, NormalizedItem


def compute_content_hash(source_type: str, key: str) -> str:
    """Stable dedup key for an item, namespaced by source type."""
    return hashlib.sha256(f"{source_type}:{key}".encode()).hexdigest()


def dedupe(items: Iterable[NormalizedItem]) -> list[NormalizedItem]:
    """Drop items sharing a content_hash, keeping first occurrence."""
    seen: set[str] = set()
    out: list[NormalizedItem] = []
    for item in items:
        if item.content_hash in seen:
            continue
        seen.add(item.content_hash)
        out.append(item)
    return out


class SourceAdapter(ABC):
    """Base class for all source adapters.

    Subclasses set ``source_type`` and implement fetch / normalize / health_check.
    ``fetch`` returns already-normalized, de-duplicated items plus conditional-GET
    state so the caller can persist it for the next poll.
    """

    source_type: str = "generic"

    @abstractmethod
    async def fetch(
        self, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        """Pull the source, honoring conditional-GET when supported."""

    @abstractmethod
    def normalize(self, raw: object) -> NormalizedItem:
        """Map one raw source record onto a NormalizedItem."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the source is reachable and parseable."""
