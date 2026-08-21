"""After the fact: why did this post do what it did? (PROJECT.md §33)

The evaluation page answers "how wrong is the model on average". This answers the
question you actually ask after posting: *this one* — was it good, and compared to
what? Four reference points, because a number alone explains nothing:

  1. what we predicted           → is the model calibrated for this kind of post
  2. your own median post        → did it beat you
  3. the corpus you've seen      → did it beat the room
  4. the first-hour curve        → did it die at the gate or fade later

Fully deterministic. No LLM writes the verdict; the numbers do.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, PostMetric, PostPrediction
from app.pipeline.benchmark import percentile_of
from app.pipeline.performance import content_type_tags
from app.pipeline.xsim import extract_features

# X front-loads distribution: a post that gets nothing in the first hour rarely recovers.
FIRST_HOUR_MINUTES = 60
# Ratio of actual to predicted beyond which the model was meaningfully wrong.
PREDICTION_TOLERANCE = 0.35


@dataclass
class Comparison:
    """One reference point, phrased as a finding."""

    label: str
    actual: float
    reference: float | None
    verdict: str  # better | similar | worse | unknown
    note: str


@dataclass
class PostMortem:
    post_id: str
    text: str
    posted_at: datetime | None = None
    hours_since_post: float | None = None
    settled: bool = False
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    impressions: int | None = None
    first_hour_likes: int | None = None
    tags: list[str] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)


# Below ~6 hours the numbers are still moving and any verdict is premature.
SETTLE_HOURS = 6.0


def _verdict(actual: float, reference: float, tolerance: float = 0.15) -> str:
    if reference <= 0:
        return "unknown"
    ratio = actual / reference
    if ratio >= 1 + tolerance:
        return "better"
    if ratio <= 1 - tolerance:
        return "worse"
    return "similar"


def _minutes_after(metric: PostMetric, posted: datetime) -> float:
    captured = metric.captured_at
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    return (captured - posted).total_seconds() / 60.0


async def _metrics(session: AsyncSession, post_id) -> list[PostMetric]:
    return list(
        (
            await session.execute(
                select(PostMetric)
                .where(PostMetric.post_id == post_id)
                .order_by(PostMetric.captured_at.asc())
            )
        ).scalars()
    )


async def post_mortem(
    session: AsyncSession,
    post: Post,
    *,
    corpus_likes: list[float] | None = None,
    now: datetime | None = None,
) -> PostMortem:
    now = now or datetime.now(UTC)
    series = await _metrics(session, post.id)
    latest = series[-1] if series else None

    posted = post.posted_at
    if posted is not None and posted.tzinfo is None:
        posted = posted.replace(tzinfo=UTC)
    hours = round((now - posted).total_seconds() / 3600, 1) if posted else None

    # PostMetric stores an absolute capture time; minutes-after-post is derived.
    first_hour = (
        next(
            (m.likes for m in series if _minutes_after(m, posted) <= FIRST_HOUR_MINUTES),
            None,
        )
        if posted is not None
        else None
    )

    mortem = PostMortem(
        post_id=str(post.id),
        text=post.text,
        posted_at=posted,
        hours_since_post=hours,
        settled=hours is not None and hours >= SETTLE_HOURS,
        likes=(latest.likes if latest and latest.likes is not None else 0),
        replies=(latest.replies if latest and latest.replies is not None else 0),
        reposts=(latest.reposts if latest and latest.reposts is not None else 0),
        impressions=latest.impressions if latest else None,
        first_hour_likes=first_hour,
        tags=content_type_tags(post.text),
    )

    if latest is None:
        mortem.lessons.append(
            "Bu gönderi için hiç metrik yok — eklenti çalışıyor mu, X'te profilini aç."
        )
        return mortem

    prediction = (
        await session.execute(
            select(PostPrediction)
            .where(PostPrediction.post_id == post.id)
            .order_by(PostPrediction.predicted_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if prediction is not None and prediction.predicted_likes:
        mortem.comparisons.append(
            Comparison(
                label="prediction",
                actual=float(mortem.likes),
                reference=float(prediction.predicted_likes),
                verdict=_verdict(mortem.likes, prediction.predicted_likes, PREDICTION_TOLERANCE),
                note=f"Model {prediction.predicted_likes} beğeni bekliyordu.",
            )
        )

    own_median = await _own_median_likes(session, exclude=post.id)
    if own_median is not None:
        mortem.comparisons.append(
            Comparison(
                label="your_median",
                actual=float(mortem.likes),
                reference=own_median,
                verdict=_verdict(mortem.likes, own_median),
                note=f"Senin ortanca gönderin {own_median:.0f} beğeni alıyor.",
            )
        )

    if corpus_likes:
        pct = percentile_of(corpus_likes, float(mortem.likes))
        mortem.comparisons.append(
            Comparison(
                label="corpus",
                actual=pct,
                reference=50.0,
                verdict="better" if pct >= 60 else "worse" if pct < 40 else "similar",
                note=f"Gördüğün tweetlerin %{pct:.0f}'ini geçti.",
            )
        )

    mortem.lessons = _lessons(post, mortem)
    return mortem


async def _own_median_likes(session: AsyncSession, *, exclude) -> float | None:
    posts = list(
        (await session.execute(select(Post).where(Post.status == "posted"))).scalars()
    )
    values: list[float] = []
    for other in posts:
        if other.id == exclude:
            continue
        latest = (
            await session.execute(
                select(PostMetric)
                .where(PostMetric.post_id == other.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is not None and latest.likes is not None:
            values.append(float(latest.likes))
    return round(statistics.median(values), 1) if len(values) >= 3 else None


def _lessons(post: Post, m: PostMortem) -> list[str]:
    """Only say things the numbers actually support."""
    out: list[str] = []
    if not m.settled:
        out.append(
            f"Henüz {m.hours_since_post or 0:.1f} saat oldu — {SETTLE_HOURS:.0f} saatten önce "
            "kesin yorum yapmak erken."
        )

    if m.first_hour_likes is not None and m.likes:
        share = m.first_hour_likes / m.likes
        if share >= 0.7:
            out.append(
                "Etkileşimin neredeyse tamamı ilk saatte geldi: dağıtım erken durmuş, "
                "gönderinin kendisi değil zamanlaması sınırlamış olabilir."
            )
        elif share <= 0.2 and m.likes >= 5:
            out.append(
                "İlk saatte az, sonrasında çok: birisi paylaşmış ya da arama üzerinden "
                "gelmiş. Bu tür gönderiler zamanlamaya daha az bağlı."
            )
    elif m.first_hour_likes is None:
        out.append("İlk saat ölçümü yok — ilk saat penceresi kaçırıldığı için hız hesaplanamadı.")

    if m.impressions and m.likes is not None:
        rate = 100.0 * m.likes / m.impressions
        if m.impressions >= 500 and rate < 0.5:
            out.append(
                f"{m.impressions} görüntülenme, %{rate:.2f} beğeni oranı — görülüyor ama "
                "harekete geçirmiyor. Sorun erişim değil, metin."
            )
        elif rate >= 2.0:
            out.append(
                f"%{rate:.2f} beğeni oranı yüksek — gören beğeniyor, sorun erişimde. "
                "Aynı fikri farklı bir saatte tekrar denemeye değer."
            )

    features = extract_features(post.text)
    if m.replies == 0 and not features.has_question:
        out.append("Hiç yanıt yok ve metinde soru da yok — yanıt, beğeninin ~10 katı ağırlıkta.")
    if m.reposts == 0 and features.shareable < 0.3:
        out.append(
            "Hiç repost yok: paylaşılacak bir şey (rakam, karşılaştırma, net iddia) taşımıyor."
        )

    pred = next((c for c in m.comparisons if c.label == "prediction"), None)
    if pred is not None and pred.reference:
        if pred.verdict == "worse":
            out.append(
                f"Model {pred.reference:.0f} bekledi, {pred.actual:.0f} geldi — bu tür "
                "gönderilerde fazla iyimser."
            )
        elif pred.verdict == "better":
            out.append(
                f"Model {pred.reference:.0f} bekledi, {pred.actual:.0f} geldi — beklenenin "
                "üstünde; kalibrasyon bunu bir sonraki tahmine yansıtacak."
            )
    return out
