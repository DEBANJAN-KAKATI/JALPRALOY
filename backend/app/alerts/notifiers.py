"""Alert delivery channels. Each notifier takes a rendered message and a recipient.

Rules (see docs/08_ALERTS_CAP.md):
  * send only on a colour UPGRADE or a new area; never re-send the same alert
  * downgrade only after two consecutive runs agree (prevents flapping)
  * every message carries the CAP status — "Exercise" in demos
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


def send_telegram(chat_id: str, text: str) -> bool:
    """Create a bot with @BotFather; users start the bot, you store their chat_id."""
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN not set; skipping")
        return False
    r = httpx.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                   json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    if r.status_code != 200:
        log.error("telegram failed: %s", r.text[:200])
    return r.status_code == 200


def send_sms(phone: str, text: str) -> bool:
    """TODO: an Indian SMS gateway requires DLT registration of the sender ID and
    message templates (TRAI rules). For the demo, Telegram + web push are enough."""
    raise NotImplementedError


def send_web_push(subscription: dict, payload: str) -> bool:
    """TODO: pywebpush with VAPID keys; the frontend service worker shows the notification."""
    raise NotImplementedError


def render_text(area: str, color_word: str, headline: str, lang: str = "en") -> str:
    # TODO: localised templates (as, bn, hi) reviewed by native speakers
    return f"<b>{color_word.upper()} · {area}</b>\n{headline}\nHelpline: 1070 / 1077 / 112"
