from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx


class TelegramProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramBotProfile:
    username: str

    @property
    def public_url(self) -> str:
        return f"https://t.me/{quote(self.username)}"


def fetch_bot_profile(token: str) -> TelegramBotProfile:
    try:
        response = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramProfileError("Telegram bot token could not be verified") from exc

    if not payload.get("ok"):
        raise TelegramProfileError("Telegram bot token is invalid")

    result = payload.get("result")
    username = result.get("username") if isinstance(result, dict) else None
    if not isinstance(username, str) or not username.strip():
        raise TelegramProfileError("Telegram bot username is missing")

    return TelegramBotProfile(username=username.strip())
