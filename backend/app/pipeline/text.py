"""Lightweight text helpers: keyword extraction and set similarity."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small, language-agnostic-ish stopword list (EN + a few TR) for keyword extraction.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but of to in on for with at by from as is are was were be been being
    this that these those it its it's you your we our they their he she his her i me my
    do does did done have has had will would can could should may might must not no yes
    new now today just about into over under more most less least very can't dont don't
    ve ile bir bu su o da de ki mi mu için çok az en ve
    """.split()
)


def keywords(text: str | None, *, max_terms: int = 20) -> set[str]:
    """Extract a set of significant lowercase tokens from text."""
    if not text:
        return set()
    terms: list[str] = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        terms.append(tok)
        if len(terms) >= max_terms:
            break
    return set(terms)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
