"""Style fingerprint from historical posts (PROJECT.md §11).

Deterministic text features (no fine-tuning). The embedding centroid of the most
successful posts is computed separately in build_style_profile.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric, StyleProfile
from app.pipeline.cost import persist_usage
from app.pipeline.text import STOPWORDS
from app.providers.base import EmbeddingProvider, LLMProvider

# Words for the STRUCTURAL features (length, caps, hooks) — apostrophes kept so "don't"
# counts as one word.
_WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)

# A term has to appear in at least this many separate posts to count as characteristic.
# Without it, one rambling post injects its whole vocabulary into "how you write".
MIN_TERM_POSTS = 2
# Below this many posts, take the most frequent terms as-is.
MIN_CORPUS_FOR_FLOOR = 8
# No stopword list is ever complete: "gerekiyor", "şekilde", "gerçekten" aren't stopwords
# but say nothing about what someone writes about. Rank by df * log(n/df) instead — a
# classic TF-IDF shape. A term in EVERY post scores exactly 0 (log 1) and drops out, while
# a term in a healthy minority scores highest. That handles background language without a
# hard cutoff, so a genuinely dominant topic still survives.
_SENT_RE = re.compile(r"[.!?]+")
_EMOJI_RE = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]"
)
_HOOK_WORDS = ("how", "why", "what", "the", "stop", "here", "you")


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


@dataclass
class StyleFingerprint:
    post_count: int = 0
    features: dict[str, float] = field(default_factory=dict)
    top_terms: list[str] = field(default_factory=list)
    summary: str = ""


def compute_style_profile(texts: list[str]) -> StyleFingerprint:
    texts = [t for t in texts if t and t.strip()]
    n = len(texts)
    if n == 0:
        return StyleFingerprint(summary="No posts yet — style profile is empty.")

    lengths, sentence_lens, questions, exclaims = [], [], [], []
    emoji_rate, hashtags, mentions, links, lists, hooks, allcaps = [], [], [], [], [], [], []
    vocab: Counter[str] = Counter()

    for t in texts:
        words = _WORD_RE.findall(t)
        sentences = [s for s in _SENT_RE.split(t) if s.strip()] or [t]
        lengths.append(len(t))
        sentence_lens.append(len(words) / max(1, len(sentences)))
        questions.append(1.0 if "?" in t else 0.0)
        exclaims.append(1.0 if "!" in t else 0.0)
        emoji_rate.append(len(_EMOJI_RE.findall(t)) / max(1, len(t)))
        hashtags.append(t.count("#"))
        mentions.append(t.count("@"))
        links.append(1.0 if "http" in t else 0.0)
        lists.append(1.0 if re.search(r"(^|\n)\s*([-*•]|\d+\.)\s", t) else 0.0)
        first = words[0].lower() if words else ""
        hooks.append(1.0 if (t.lstrip().startswith(("?",)) or first in _HOOK_WORDS) else 0.0)
        allcaps.append(sum(1 for w in words if w.isupper() and len(w) > 1) / max(1, len(words)))
        # Count each term ONCE per post: frequency across posts is what makes a term
        # characteristic, whereas raw frequency just favours whoever repeated themselves.
        seen_here = set()
        for w in words:
            wl = w.lower().strip("'")
            if len(wl) >= 3 and wl not in STOPWORDS and wl not in seen_here:
                seen_here.add(wl)
                vocab[wl] += 1

    features = {
        "avg_length": _mean([float(x) for x in lengths]),
        "avg_sentence_length": _mean(sentence_lens),
        "question_rate": _mean(questions),
        "exclaim_rate": _mean(exclaims),
        "emoji_rate": _mean(emoji_rate),
        "hashtag_per_post": _mean([float(x) for x in hashtags]),
        "mention_per_post": _mean([float(x) for x in mentions]),
        "link_rate": _mean(links),
        "list_rate": _mean(lists),
        "hook_rate": _mean(hooks),
        "allcaps_rate": _mean(allcaps),
    }
    # Demanding cross-post evidence only makes sense with a real corpus; on a handful of
    # posts it would empty the list entirely and leave the profile with nothing to say.
    floor = MIN_TERM_POSTS if n >= MIN_CORPUS_FOR_FLOOR else 1
    scored = [
        (w, df * math.log(n / df))
        for w, df in vocab.items()
        if df >= floor and df < n  # df == n means it's in every post: zero information
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    top_terms = [w for w, _ in scored[:15]]

    tone = "energetic" if features["exclaim_rate"] > 0.3 else "measured"
    curiosity = "inquisitive" if features["question_rate"] > 0.35 else "declarative"
    length_word = "punchy" if features["avg_length"] < 160 else "long-form"
    summary = (
        f"{tone}, {curiosity}, {length_word}. "
        f"~{int(features['avg_length'])} chars/post, "
        f"{int(features['question_rate'] * 100)}% ask a question, "
        f"emoji {'used' if features['emoji_rate'] > 0.002 else 'rare'}. "
        f"Frequent terms: {', '.join(top_terms[:6]) or '—'}."
    )
    return StyleFingerprint(post_count=n, features=features, top_terms=top_terms, summary=summary)


_TOPICS_SYSTEM = (
    "You are given a set of posts by one author. Reply with STRICT JSON: "
    '{"topics": ["<subject>", ...]}. '
    "List up to 8 SUBJECTS this person actually writes about — concrete things like "
    "'Docker', 'AI agents', 'web security', 'freelancing'. Never list filler words, "
    "generic verbs, or adjectives. Use the author's own language for the subjects. "
    "No markdown, no prose outside the JSON."
)


async def derive_topics(texts: list[str], llm: LLMProvider, *, limit: int = 40) -> list[str]:
    """Ask what this person writes about, instead of counting words.

    Word frequency can't tell a common Turkish word from a topical one: within a
    single-author corpus there is no reference for "normal" language, so filler like
    "gerekiyor" or "gerçekten" scores exactly like a real subject. Stopword lists are
    endless whack-a-mole. One model call per rebuild (daily) settles it properly.
    """
    sample = [t.strip() for t in texts if t and t.strip()][:limit]
    if not sample:
        return []
    joined = "\n".join(f"- {t[:280]}" for t in sample)
    raw = await llm.generate(
        f"Posts:\n{joined}\n\nReturn the JSON.",
        system=_TOPICS_SYSTEM,
        temperature=0.2,
        max_tokens=300,
    )
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    topics = data.get("topics")
    if not isinstance(topics, list):
        return []
    out: list[str] = []
    for t in topics:
        label = str(t).strip()
        if label and label.lower() not in {o.lower() for o in out}:
            out.append(label[:60])
    return out[:8]


async def build_style_profile(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    key: str = "default",
    top_k: int = 25,
    llm: LLMProvider | None = None,
) -> StyleProfile:
    """Recompute + persist the style profile from all imported posts.

    When an LLM is supplied the subjects come from it rather than word counting, which is
    the only reliable way to tell a topic from ordinary language in a one-author corpus.
    """
    posts = list((await session.execute(select(Post))).scalars())
    fingerprint = compute_style_profile([p.text for p in posts])

    if llm is not None and posts:
        topics = await derive_topics([p.text for p in posts], llm)
        if topics:
            fingerprint.top_terms = topics
            head, _, _ = fingerprint.summary.rpartition("Frequent terms:")
            fingerprint.summary = f"{head}Writes about: {', '.join(topics[:6])}."
        await persist_usage(session, purpose="style")

    centroid: list[float] | None = None
    if posts:
        # Rank posts by latest likes to embed the "successful" cluster (PROJECT.md §11).
        scored: list[tuple[int, Post]] = []
        for p in posts:
            latest = (
                await session.execute(
                    select(PostMetric)
                    .where(PostMetric.post_id == p.id)
                    .order_by(PostMetric.captured_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            scored.append(((latest.likes or 0) if latest else 0, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_texts = [p.text for _, p in scored[:top_k]]
        vectors = await embedder.embed_texts(top_texts)
        if vectors:
            dim = len(vectors[0])
            centroid = [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]

    profile = (
        await session.execute(select(StyleProfile).where(StyleProfile.key == key))
    ).scalar_one_or_none()
    if profile is None:
        profile = StyleProfile(key=key)
        session.add(profile)
    profile.post_count = fingerprint.post_count
    profile.features = {**fingerprint.features, "top_terms": fingerprint.top_terms}
    profile.summary = fingerprint.summary
    profile.centroid = centroid
    return profile
