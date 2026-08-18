"""Event clustering: group ContentItems that describe the same real-world event.

Combines multiple signals (PROJECT.md §6) — NOT embeddings alone:
  - embedding cosine similarity
  - keyword / entity overlap (Jaccard)
  - time proximity (within a window)
  - shared canonical URL

An online, single-pass clusterer: each item joins the best-matching existing
cluster above a threshold, otherwise it seeds a new cluster.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

from app.pipeline.text import jaccard

# Signal weights (sum ~1.0). Tunable; scoring stays explainable.
W_EMBED = 0.55
W_KEYWORD = 0.30
W_TIME = 0.10
W_URL = 0.05

# 0.60 merged genuinely different stories from the same outlet (e5 rates any two
# "OpenAI announces X" headlines as similar). 0.72 keeps distinct stories apart.
DEFAULT_THRESHOLD = 0.72
DEFAULT_WINDOW = timedelta(hours=72)


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, dot / (na * nb))


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


@dataclass
class ClusterItem:
    id: str
    title: str | None = None
    embedding: list[float] | None = None
    keywords: set[str] = field(default_factory=set)
    url: str | None = None
    timestamp: datetime | None = None


@dataclass
class Cluster:
    items: list[ClusterItem] = field(default_factory=list)
    centroid: list[float] | None = None
    keywords: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def add(self, item: ClusterItem) -> None:
        self.items.append(item)
        self.keywords |= item.keywords
        canon = canonical_url(item.url)
        if canon:
            self.urls.add(canon)
        if item.timestamp:
            self.first_seen = min(self.first_seen or item.timestamp, item.timestamp)
            self.last_seen = max(self.last_seen or item.timestamp, item.timestamp)
        if item.embedding:
            self._update_centroid(item.embedding)

    def _update_centroid(self, embedding: list[float]) -> None:
        n = sum(1 for it in self.items if it.embedding)
        if self.centroid is None or n <= 1:
            self.centroid = list(embedding)
            return
        # incremental mean
        self.centroid = [
            c + (e - c) / n for c, e in zip(self.centroid, embedding, strict=False)
        ]


def _time_factor(item: ClusterItem, cluster: Cluster, window: timedelta) -> float:
    if not item.timestamp or (cluster.first_seen is None and cluster.last_seen is None):
        return 0.0
    ref = cluster.last_seen or cluster.first_seen
    delta = abs((item.timestamp - ref).total_seconds())
    span = window.total_seconds()
    return max(0.0, 1.0 - delta / span) if span else 0.0


def within_window(item: ClusterItem, cluster: Cluster, window: timedelta) -> bool:
    if not item.timestamp or (cluster.first_seen is None and cluster.last_seen is None):
        return True  # no time info -> don't exclude on time
    ref = cluster.last_seen or cluster.first_seen
    return abs(item.timestamp - ref) <= window


def score(item: ClusterItem, cluster: Cluster, window: timedelta) -> float:
    """Combined similarity of an item to a cluster in [0, 1]."""
    # A shared canonical URL is a strong same-event signal.
    if canonical_url(item.url) and canonical_url(item.url) in cluster.urls:
        return 1.0
    emb = cosine(item.embedding, cluster.centroid)
    kw = jaccard(item.keywords, cluster.keywords)
    tf = _time_factor(item, cluster, window)
    url = 1.0 if canonical_url(item.url) in cluster.urls else 0.0
    return W_EMBED * emb + W_KEYWORD * kw + W_TIME * tf + W_URL * url


def cluster_items(
    items: list[ClusterItem],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    window: timedelta = DEFAULT_WINDOW,
) -> list[Cluster]:
    """Single-pass online clustering. Order-dependent but deterministic per input."""
    clusters: list[Cluster] = []
    for item in items:
        best: Cluster | None = None
        best_score = 0.0
        for cluster in clusters:
            if not within_window(item, cluster, window):
                continue
            s = score(item, cluster, window)
            if s > best_score:
                best_score, best = s, cluster
        if best is not None and best_score >= threshold:
            best.add(item)
        else:
            new = Cluster()
            new.add(item)
            clusters.append(new)
    return clusters
