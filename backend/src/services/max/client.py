"""Thin client for the MAX Bot API (https://platform-api2.max.ru).

Only the handful of calls the product actually makes. Notes that cost time to rediscover:

- the token goes in an ``Authorization`` header; passing it as a query parameter was
  removed by the platform;
- production updates must arrive by webhook (``POST /subscriptions``) over HTTPS with a
  certificate from a trusted CA - long polling is documented as development-only;
- the platform rate-limits to 30 rps, so every call here is a single request with a short
  timeout and no retry storm.

Every method is fail-soft: a delivery problem must never take down the webhook handler,
because MAX retries deliveries and a 500 from us just amplifies the load.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Where the Ministry bundle can be found, most specific first. See infra/certs/README.md
# for provenance and fingerprints.
_CA_CANDIDATES = (
    # Copied in by backend/Dockerfile.
    Path("/app/certs/russian-trusted-ca.crt"),
    # Running from a checkout: local uvicorn, scripts/max_setup.py, tests.
    Path(__file__).resolve().parents[4] / "infra" / "certs" / "russian-trusted-ca.crt",
    # Last resort: a system store somebody ran update-ca-certificates against.
    Path("/etc/ssl/certs/ca-certificates.crt"),
)


def resolve_ca_bundle(explicit: str | None = None) -> str | bool:
    """What to hand httpx as ``verify``.

    Note what does *not* work: installing the Ministry CA into the system trust store.
    httpx verifies against certifi's bundle, so ``update-ca-certificates`` reaches curl and
    openssl but never this client - the handshake just times out. The bundle has to be named
    explicitly, which is why the Dockerfile also drops it at a fixed path.

    Trusting only the Ministry chain is deliberate: this client talks to *.max.ru and
    nothing else, so a narrower trust anchor is the tighter choice.
    """
    if explicit and os.path.exists(explicit):
        return explicit
    for candidate in _CA_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return True


class MaxApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class MaxBotProfile:
    user_id: int
    name: str
    username: str

    @property
    def public_url(self) -> str:
        return f"https://max.ru/{self.username}" if self.username else ""


def button_callback(text: str, payload: str) -> dict[str, Any]:
    return {"type": "callback", "text": text, "payload": payload}


def button_link(text: str, url: str) -> dict[str, Any]:
    return {"type": "link", "text": text, "url": url}


def button_open_app(text: str, url: str) -> dict[str, Any]:
    """Opens the mini app inside the bot - the one button that makes this a MAX product."""
    return {"type": "open_app", "text": text, "url": url}


def button_request_contact(text: str) -> dict[str, Any]:
    return {"type": "request_contact", "text": text}


def inline_keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


class MaxBotClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://platform-api2.max.ru",
        ca_bundle: str | None = None,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._verify = resolve_ca_bundle(ca_bundle)

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self._token:
            raise MaxApiError("MAX bot token is not configured")
        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": self._token},
                timeout=REQUEST_TIMEOUT,
                verify=self._verify,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise MaxApiError(f"MAX API request failed: {exc}") from exc

        if response.status_code >= 400:
            # The body carries the platform's own reason; keep it, it is the only way to
            # tell "bad token" from "chat not found" without guessing.
            raise MaxApiError(f"MAX API {response.status_code}: {response.text[:300]}")
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def get_me(self) -> MaxBotProfile:
        payload = self._request("GET", "/me")
        return MaxBotProfile(
            user_id=int(payload.get("user_id") or 0),
            name=str(payload.get("name") or ""),
            username=str(payload.get("username") or ""),
        )

    def set_commands(self, commands: list[dict[str, str]]) -> None:
        self._request("PATCH", "/me/commands", json={"commands": commands})

    def subscribe_webhook(self, url: str, *, update_types: list[str] | None = None) -> None:
        body: dict[str, Any] = {"url": url}
        if update_types:
            body["update_types"] = update_types
        self._request("POST", "/subscriptions", json=body)

    def list_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/subscriptions")

    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        buttons: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        body: dict[str, Any] = {"text": text}
        if buttons:
            body["attachments"] = [inline_keyboard(buttons)]
        # chat_id is a query parameter for POST /messages; the token stays in the header.
        self._request("POST", "/messages", params={"chat_id": chat_id}, json=body)

    def try_send_message(
        self,
        *,
        chat_id: int,
        text: str,
        buttons: list[list[dict[str, Any]]] | None = None,
    ) -> bool:
        """Send and swallow failures - used on paths where delivery is best-effort."""
        try:
            self.send_message(chat_id=chat_id, text=text, buttons=buttons)
            return True
        except MaxApiError:
            logger.warning("max_send_failed chat_id=%s", chat_id, exc_info=True)
            return False

    def answer_callback(self, callback_id: str, *, notification: str = "") -> None:
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        try:
            self._request("POST", "/answers", params={"callback_id": callback_id}, json=body)
        except MaxApiError:
            # A stale callback id is normal (the user tapped an old message); never surface it.
            logger.debug("max_answer_callback_failed", exc_info=True)
