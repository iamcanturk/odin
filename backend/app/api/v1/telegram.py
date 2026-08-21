"""Telegram webhook: your pocket remote for ODIN.

Inbound only. Telegram POSTs updates here and we act on the text. Everything that
would publish still routes through an X intent link the user taps — the bot has no
X credentials and never will from this endpoint.

Auth is Telegram's secret_token, echoed back on every update as a header. The chat id
is checked too: a leaked URL alone must not let a stranger write drafts into your
system.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import Post
from app.pipeline.cadence import cadence
from app.providers.telegram import get_telegram, intent_url

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

HELP = (
    "<b>ODIN</b>\n\n"
    "Bir şey yaz → taslak olur.\n"
    "/durum — bu haftaki tempon\n"
    "/kuyruk — sıradaki taslaklar\n"
    "/yardim — bu mesaj"
)


class WebhookAck(BaseModel):
    ok: bool = True
    action: str = "ignored"


@router.post("/webhook", response_model=WebhookAck)
async def webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> WebhookAck:
    settings = get_settings()
    secret = settings.telegram_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Telegram webhook not configured")
    if x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="Bad secret token")

    update: dict[str, Any] = await request.json()
    message = update.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    text = (message.get("text") or "").strip()

    # A valid secret in the wrong chat is still the wrong chat.
    if settings.telegram_chat_id and chat_id != settings.telegram_chat_id:
        log.warning("telegram.foreign_chat", chat_id=chat_id)
        raise HTTPException(status_code=403, detail="Unknown chat")
    if not text:
        return WebhookAck(action="empty")

    telegram = get_telegram()
    command = text.split()[0].lower().lstrip("/")

    if command in {"start", "yardim", "help"}:
        await telegram.send(HELP)
        return WebhookAck(action="help")

    if command == "durum":
        c = await cadence(session)
        await telegram.send(
            f"<b>Bu hafta</b>\n{c.posted}/{c.goal} paylaşım — "
            f"{'hedefte' if c.on_track else 'geride'}.\n"
            f"{c.days_left} gün kaldı, günde {c.per_day_needed} gerekiyor."
        )
        return WebhookAck(action="status")

    if command == "kuyruk":
        queued = list(
            (
                await session.execute(
                    select(Post)
                    .where(Post.scheduled_for.is_not(None), Post.status != "posted")
                    .order_by(Post.scheduled_for.asc())
                    .limit(5)
                )
            ).scalars()
        )
        if not queued:
            await telegram.send("Kuyruk boş.")
            return WebhookAck(action="queue_empty")
        lines = [
            f"• {p.scheduled_for:%d.%m %H:%M} — {p.text[:80]}"
            for p in queued
            if p.scheduled_for
        ]
        await telegram.send("<b>Kuyruk</b>\n" + "\n".join(lines))
        return WebhookAck(action="queue")

    # Anything else is a draft. Saved in ODIN, and handed straight back with a
    # post link so you can send it without opening the web UI.
    post = Post(
        platform="x",
        text=text,
        status="draft",
        origin="generated",
        angle="telegram",
    )
    session.add(post)
    await session.commit()

    await telegram.send(
        f"Taslak kaydedildi ({len(text)} karakter).",
        buttons=[("𝕏 Paylaş", intent_url(text))],
    )
    return WebhookAck(action="draft")
