"""Lightweight text helpers: keyword extraction and set similarity."""

from __future__ import annotations

import re

# Unicode-aware: the old [a-z0-9]+ silently truncated every Turkish word at its first
# non-ASCII letter, so "yazdım" became "yazd" and "hesabı" became "hesab". Those fragments
# then surfaced as the user's "frequent terms", which was nonsense.
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

_EN_STOPWORDS = """
    a an the and or but of to in on for with at by from as is are was were be been being
    this that these those it its you your we our they their he she his her i me my
    do does did done have has had will would can could should may might must not no yes
    new now today just about into over under more most less least very dont
    """.split()

# Turkish is agglutinative and function-word heavy; without a real list the "top terms"
# are just the most common words in the language (ama, abi, ben, sonra...) rather than
# anything characteristic of how this person writes.
_TR_STOPWORDS = """
    ve ile bir bu şu o da de ki mi mı mu mü için çok az en ama fakat ancak veya ya
    ben sen biz siz onlar bana sana bize size ona onu onun benim senin bizim sizin
    ne neden nasıl niye kim hangi nerede nereye zaman şey şeyler
    var yok değil olan olarak oldu olur olacak olmak etmek yapmak
    daha sonra önce şimdi bugün dün yarın hep hiç her bazı kendi gibi kadar
    diye ise ise de yani ayrıca hatta zaten tabii evet hayır
    abi kanka lan yani hani işte falan filan mesela
    """.split()

STOPWORDS: frozenset[str] = frozenset(_EN_STOPWORDS + _TR_STOPWORDS)


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
