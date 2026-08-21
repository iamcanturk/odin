"""Telegram as ODIN's push channel and pocket remote.

Why this exists: notifications that live only in a web app you have to remember to
open aren't notifications. Telegram reaches your phone.

What it can and cannot do, plainly. ODIN has no X write credentials — publishing has
always gone through X's intent URL with you pressing the button, and that doesn't
change here. So the bot pushes the draft *and a one-tap link that opens X with the
text already filled in*. It never posts on your behalf, because it can't, and
building something that looked like it could would be a lie in the UI.

Inbound works too: send the bot a line and it becomes a draft in ODIN.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx
import structlog

log = structlog.get_logger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 15.0
# Telegram rejects anything longer; drafts are far shorter but source text isn't.
MAX_MESSAGE = 4096


def intent_url(text: str, url: str | None = None) -> str:
    """The same X intent URL the web UI uses — one tap, you press Post."""
    body = f"{text}\n\n{url}" if url else text
    return f"https://x.com/intent/post?text={quote(body)}"


@dataclass
class SendResult:
    ok: bool
    error: str | None = None


class TelegramClient:
    """Thin wrapper. Never raises: a dead notification channel must not break a cron."""

    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(
        self,
        text: str,
        *,
        buttons: list[tuple[str, str]] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> SendResult:
        """Send a message, optionally with URL buttons as [(label, url), ...]."""
        if not self.configured:
            return SendResult(ok=False, error="telegram not configured")

        payload: dict[str, object] = {
            "chat_id": self.chat_id,
            "text": text[:MAX_MESSAGE],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": label, "url": url}] for label, url in buttons]
            }

        owns = client is None
        client = client or httpx.AsyncClient(timeout=TIMEOUT)
        try:
            response = await client.post(
                API.format(token=self.token, method="sendMessage"), json=payload
            )
            if response.status_code != 200:
                # Telegram puts the real reason in the body, not the status line.
                detail = response.text[:200]
                log.warning("telegram.send_failed", status=response.status_code, detail=detail)
                return SendResult(ok=False, error=detail)
            return SendResult(ok=True)
        except httpx.HTTPError as exc:
            log.warning("telegram.send_error", error=str(exc))
            return SendResult(ok=False, error=str(exc))
        finally:
            if owns:
                await client.aclose()

    async def set_webhook(self, url: str, secret: str) -> SendResult:
        """Point Telegram at our endpoint. The secret arrives as a header on each update."""
        if not self.token:
            return SendResult(ok=False, error="telegram not configured")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.post(
                    API.format(token=self.token, method="setWebhook"),
                    json={
                        "url": url,
                        "secret_token": secret,
                        "allowed_updates": ["message"],
                    },
                )
            except httpx.HTTPError as exc:
                return SendResult(ok=False, error=str(exc))
        return (
            SendResult(ok=True)
            if response.status_code == 200
            else SendResult(ok=False, error=response.text[:200])
        )


def get_telegram() -> TelegramClient:
    from app.core.config import get_settings

    settings = get_settings()
    return TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
