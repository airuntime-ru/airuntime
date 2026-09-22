"""MAX surface: launch-data verification, storefront generation and the end-to-end flow.

The happy path is deliberately exercised through the real HTTP endpoints with a fake MAX
API, because the thing worth protecting is the whole chain - owner writes one message,
storefront exists, customer books, owner gets it in chat - not any single function.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.logging_setup import RedactWebhookSecret
from src.db.models.max_platform import MaxLead, MaxOwner, MaxService
from src.services.agent.events import TurnFinished
from src.services.max import bot as max_bot
from src.services.max import generator, storefronts
from src.services.max.client import MaxApiError, MaxBotClient, button_open_app
from src.services.max.init_data import InitDataError, verify_contact_hash, verify_init_data
from src.services.max.schema import ServiceConfig, normalise, slugify

BOT_TOKEN = "test-max-bot-token"
WEBHOOK_SECRET = "webhook-secret-for-tests"
OWNER_ID = 500100
CUSTOMER_ID = 500200


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def build_init_data(
    *,
    user_id: int,
    token: str = BOT_TOKEN,
    start_param: str = "",
    auth_date: int | None = None,
    first_name: str = "Иван",
) -> str:
    """Produce launch parameters exactly the way MAX documents them."""
    payload: dict[str, str] = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "chat": json.dumps({"id": user_id, "type": "DIALOG"}, ensure_ascii=False),
        "query_id": "0ac1f2b0-0000-4000-8000-000000000000",
        "user": json.dumps(
            {"id": user_id, "first_name": first_name, "last_name": "Петров"},
            ensure_ascii=False,
        ),
    }
    if start_param:
        payload["start_param"] = start_param

    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, launch_params.encode(), hashlib.sha256).hexdigest()

    encoded = "&".join(f"{key}={quote(value, safe='')}" for key, value in payload.items())
    return f"{encoded}&hash={signature}"


class FakeMaxApi:
    """Records what the bot would have sent instead of calling platform-api2.max.ru."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.callbacks: list[str] = []
        self.actions: list[dict[str, Any]] = []
        # Set to a MaxApiError to make the next send with a picture fail with it.
        self.refuse_images_with: Exception | None = None

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        outer = self

        def send_message(self: MaxBotClient, **kwargs: Any) -> None:
            if kwargs.get("image_url") and outer.refuse_images_with is not None:
                raise outer.refuse_images_with
            outer.messages.append({"buttons": [], **kwargs})

        def answer_callback(
            self: MaxBotClient, callback_id: str, *, notification: str = ""
        ) -> None:
            outer.callbacks.append(notification)

        def mark_seen(self: MaxBotClient, chat_id: int) -> None:
            outer.actions.append({"chat_id": chat_id, "action": "mark_seen"})

        monkeypatch.setattr(MaxBotClient, "send_message", send_message)
        monkeypatch.setattr(MaxBotClient, "answer_callback", answer_callback)
        monkeypatch.setattr(MaxBotClient, "mark_seen", mark_seen)

    @property
    def texts(self) -> list[str]:
        return [message["text"] for message in self.messages]

    def buttons(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        return [button for row in message["buttons"] or [] for button in row]


@pytest.fixture()
def max_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "max_bot_username", "airuntime_bot")
    monkeypatch.setattr(settings, "max_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "max_miniapp_url", "https://airuntime.ru/max")


@pytest.fixture()
def fake_api(monkeypatch: pytest.MonkeyPatch) -> FakeMaxApi:
    api = FakeMaxApi()
    api.install(monkeypatch)
    return api


@pytest.fixture()
def stub_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the LLM with a deterministic storefront - the model itself is not under test."""

    async def generate_config(prompt: str) -> tuple[ServiceConfig, bool]:
        return (
            normalise(
                ServiceConfig.model_validate(
                    {
                        "kind": "booking",
                        "title": "Автосервис на Лесной",
                        "tagline": "Запишитесь за минуту",
                        "items": [
                            {"title": "Диагностика", "price_rub": 1500, "duration_min": 60},
                            {"title": "Замена масла", "price_rub": 900},
                        ],
                        "slots": ["Сегодня 14:00", "Завтра 10:00"],
                    }
                )
            ),
            True,
        )

    async def apply_edit(config: ServiceConfig, instruction: str) -> tuple[ServiceConfig, bool]:
        data = config.model_dump()
        data["items"].append({"title": "Шиномонтаж", "price_rub": 2400})
        return normalise(ServiceConfig.model_validate(data)), True

    monkeypatch.setattr(storefronts, "generate_config", generate_config)
    monkeypatch.setattr(storefronts, "apply_edit", apply_edit)


def webhook(client: TestClient, update: dict[str, Any]) -> None:
    response = client.post(f"/api/v1/max/webhook/{WEBHOOK_SECRET}", json=update)
    assert response.status_code == 200


def owner_headers(user_id: int = OWNER_ID) -> dict[str, str]:
    return {"X-Max-Init-Data": build_init_data(user_id=user_id)}


def customer_headers(slug: str, user_id: int = CUSTOMER_ID) -> dict[str, str]:
    return {"X-Max-Init-Data": build_init_data(user_id=user_id, start_param=slug)}


BRIEF = "Автосервис на Лесной: диагностика 1500, замена масла 900, с 9 до 20"


def create_storefront(client: TestClient, user_id: int = OWNER_ID, brief: str = BRIEF) -> dict:
    """What the owner's "Собрать AIRuntime" button does."""
    response = client.post(
        "/api/v1/max/miniapp/owner/services", json={"brief": brief}, headers=owner_headers(user_id)
    )
    assert response.status_code == 201, response.text
    return response.json()


def book(client: TestClient, slug: str, **fields: str) -> dict:
    response = client.post(
        "/api/v1/max/miniapp/lead",
        json={"slug": slug, "item_title": "Диагностика", "customer_name": "Пётр", **fields},
        headers=customer_headers(slug),
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------------------
# Launch data
# --------------------------------------------------------------------------------------


class TestInitDataVerification:
    def test_accepts_genuine_launch_parameters(self) -> None:
        context = verify_init_data(
            build_init_data(user_id=OWNER_ID, start_param="avtoservis"), BOT_TOKEN
        )
        assert context.user_id == OWNER_ID
        assert context.start_param == "avtoservis"
        assert context.display_name == "Иван Петров"

    def test_rejects_tampered_user_id(self) -> None:
        forged = build_init_data(user_id=OWNER_ID).replace(str(OWNER_ID), str(OWNER_ID + 1))
        with pytest.raises(InitDataError):
            verify_init_data(forged, BOT_TOKEN)

    def test_rejects_other_bot_token(self) -> None:
        with pytest.raises(InitDataError):
            verify_init_data(build_init_data(user_id=OWNER_ID), "someone-elses-token")

    def test_rejects_stale_launch_parameters(self) -> None:
        stale = build_init_data(user_id=OWNER_ID, auth_date=int(time.time()) - 7200)
        with pytest.raises(InitDataError):
            verify_init_data(stale, BOT_TOKEN)

    def test_rejects_duplicated_hash(self) -> None:
        # A second hash is the classic way past a parser that builds a dict first.
        with pytest.raises(InitDataError):
            verify_init_data(build_init_data(user_id=OWNER_ID) + "&hash=deadbeef", BOT_TOKEN)

    def test_rejects_empty_payload(self) -> None:
        with pytest.raises(InitDataError):
            verify_init_data("", BOT_TOKEN)

    def test_contact_hash_matches_only_the_signed_number(self) -> None:
        payload = "\n".join(["authDate=1771409719", "phone=79990001122", "userId=67890"])
        signature = hmac.new(BOT_TOKEN.encode(), payload.encode(), hashlib.sha256).hexdigest()
        assert verify_contact_hash(
            auth_date="1771409719",
            phone="79990001122",
            user_id=67890,
            received_hash=signature,
            bot_token=BOT_TOKEN,
        )
        assert not verify_contact_hash(
            auth_date="1771409719",
            phone="79990009999",
            user_id=67890,
            received_hash=signature,
            bot_token=BOT_TOKEN,
        )


# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------


class TestWebhookSecretRedaction:
    """MAX cannot send a header with its deliveries, so the shared secret lives in the
    path - and uvicorn's access logger would otherwise print it on every delivery."""

    def _redacted(self, msg: str, args: object = None) -> str:
        record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, msg, args, None)
        RedactWebhookSecret().filter(record)
        return record.getMessage()

    def test_strips_the_secret_from_an_access_log_line(self) -> None:
        line = self._redacted(
            '%s - "%s %s HTTP/1.1" %d',
            ("10.0.0.1:1", "POST", "/api/v1/max/webhook/n9fZAVHUg3xgPF5Yl0tET5", 200),
        )
        assert "n9fZAVHUg3xgPF5Yl0tET5" not in line
        assert "/api/v1/max/webhook/<secret>" in line

    def test_strips_the_secret_from_a_plain_message(self) -> None:
        line = self._redacted("delivered to /api/v1/max/webhook/abc123 ok")
        assert "abc123" not in line
        assert "/api/v1/max/webhook/<secret>" in line

    def test_leaves_unrelated_lines_alone(self) -> None:
        assert self._redacted("GET /api/v1/projects/42") == "GET /api/v1/projects/42"
        assert self._redacted("max_webhook_failed type=%s", ("message_created",)) == (
            "max_webhook_failed type=message_created"
        )


# --------------------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------------------


class TestConnectRetry:
    """platform-api2.max.ru resolves to several nodes and the handshake intermittently
    hangs. One retry is the difference between a 200ms hiccup and a lead that silently
    never reaches the owner's chat."""

    def _client(self) -> MaxBotClient:
        return MaxBotClient(BOT_TOKEN, base_url="https://platform-api2.max.ru")

    def test_retries_once_when_the_connection_never_lands(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(method)
            if len(calls) == 1:
                raise httpx.ConnectTimeout("handshake timed out")
            return httpx.Response(200, json={"user_id": 1, "username": "bot", "name": "Bot"})

        monkeypatch.setattr(httpx, "request", request)
        assert self._client().get_me().username == "bot"
        assert len(calls) == 2

    def test_gives_up_after_the_second_connect_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(method)
            raise httpx.ConnectError("no route")

        monkeypatch.setattr(httpx, "request", request)
        with pytest.raises(MaxApiError, match="unreachable after 2 attempts"):
            self._client().get_me()
        assert len(calls) == 2

    def test_does_not_retry_a_read_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(method)
            raise httpx.ReadTimeout("server went quiet")

        monkeypatch.setattr(httpx, "request", request)
        # The platform may already have sent the message; a retry would duplicate it.
        with pytest.raises(MaxApiError):
            self._client().send_message(chat_id=1, text="hi")
        assert len(calls) == 1

    def test_does_not_retry_a_rejected_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(method)
            return httpx.Response(401, text="bad token")

        monkeypatch.setattr(httpx, "request", request)
        with pytest.raises(MaxApiError, match="401"):
            self._client().get_me()
        assert len(calls) == 1

    def test_mark_seen_posts_the_chat_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            captured.update(method=method, url=url, json=kwargs.get("json"))
            return httpx.Response(200, json={"success": True})

        monkeypatch.setattr(httpx, "request", request)
        self._client().mark_seen(777001)
        assert captured["method"] == "POST"
        assert captured["url"] == "https://platform-api2.max.ru/chats/777001/actions"
        assert captured["json"] == {"action": "mark_seen"}

    def test_mark_seen_swallows_api_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
            return httpx.Response(500, text="nope")

        monkeypatch.setattr(httpx, "request", request)
        self._client().mark_seen(1)


class TestOpenAppButtonShape:
    """The button that opens the mini app is the product's main CTA. Its shape comes from
    OpenAppButton in MAX's OpenAPI schema (github.com/max-messenger/api-schema), and the
    platform does not check it when the message is sent - a wrong shape is accepted and
    then simply opens nothing when tapped. Two wrong shapes shipped before this one."""

    def test_web_app_names_the_bot_and_payload_carries_the_slug(self) -> None:
        button = button_open_app(
            "Открыть AIRuntime", "t403_hakaton_max_bot", "avtoservis", contact_id=395683755
        )
        assert button == {
            "type": "open_app",
            "text": "Открыть AIRuntime",
            "web_app": "t403_hakaton_max_bot",
            "contact_id": 395683755,
            "payload": "avtoservis",
        }

    def test_owner_view_carries_no_payload(self) -> None:
        # The mini app routes on start_param alone: none means the owner's cabinet.
        assert "payload" not in button_open_app("Заявки", "t403_hakaton_max_bot")

    def test_never_an_address(self) -> None:
        # `url` is ignored on this type (`Field 'webApp' cannot be null`), and a URL in
        # web_app is accepted by the API but opens nothing.
        button = button_open_app("Открыть", "t403_hakaton_max_bot", "x")
        assert "url" not in button
        assert "://" not in button["web_app"]

    def test_slugs_fit_the_payload_pattern(self) -> None:
        # payload must match ^[\w-]*$ and stay within 512 characters.
        slug = slugify("Кофейня «Утро» на Мира, 12")
        assert re.fullmatch(r"[\w-]*", slug) and len(slug) <= 512


class TestGeneratorFailsLoudly:
    """A provider adapter signals a failed turn with an event, not an exception. Collecting
    only TextDelta turned `the model is misconfigured` into `the model said nothing`, and
    the storefront wizard then served its keyword fallback as if it were an answer."""

    def test_raises_when_the_turn_ends_in_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class ErroringProvider:
            def build_messages(self, history: list, text: str) -> list:
                return [{"role": "user", "content": text}]

            async def stream_turn(self, **kwargs: Any):
                yield TurnFinished(
                    stop_reason="error", error='HTTP 400: {"error":"Model not found"}'
                )

        monkeypatch.setattr(generator, "_resolve_llm", lambda: ("routerai", "nope", "key"))
        monkeypatch.setattr(generator, "get_agent_provider", lambda _name: ErroringProvider())

        with pytest.raises(RuntimeError, match="Model not found"):
            asyncio.run(generator._complete("system", "Автосервис"))

    def test_a_turn_that_wrote_nothing_is_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The proxy hands the model a tool set we never asked for, and one turn in three
        # comes back as a `bash` call with no text. Asking again is what stands between the
        # owner's real prices and a stub.
        replies = ["", '{"kind": "booking", "title": "Автосервис на Лесной", "items": []}']

        async def complete(system_prompt: str, user_text: str) -> str:
            return replies.pop(0)

        monkeypatch.setattr(generator, "_complete", complete)
        config, used_llm = asyncio.run(generator.generate_config("Автосервис"))
        assert used_llm is True
        assert config.title == "Автосервис на Лесной"
        assert replies == []

    def test_an_unconfigured_provider_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        async def complete(system_prompt: str, user_text: str) -> str:
            nonlocal calls
            calls += 1
            raise generator.LlmUnavailable("No LLM provider is configured")

        monkeypatch.setattr(generator, "_complete", complete)
        config, used_llm = asyncio.run(generator.generate_config("Кофейня на Мира"))
        assert used_llm is False
        assert calls == 1, "a missing key does not get better on the third try"

    def test_the_fallback_still_catches_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Loud in the log, but the owner must still get a draft they can edit.
        async def boom(*args: Any, **kwargs: Any) -> str:
            raise RuntimeError("routerai/nope: HTTP 400")

        monkeypatch.setattr(generator, "_complete", boom)
        config, used_llm = asyncio.run(generator.generate_config("Кофейня на Мира"))
        assert used_llm is False
        assert config.kind == "menu"


# --------------------------------------------------------------------------------------
# Storefront schema
# --------------------------------------------------------------------------------------


class TestServiceConfig:
    def test_clamps_untrusted_model_output(self) -> None:
        config = ServiceConfig.model_validate(
            {
                "kind": "spaceship",
                "title": "Кафе",
                "accent": "javascript:alert(1)",
                "items": [{"title": f"Позиция {index}"} for index in range(40)],
                "slots": [f"Слот {index}" for index in range(30)],
            }
        )
        assert config.kind == "booking"
        assert config.accent == "#2E7CF6"
        assert len(config.items) == 24
        assert len(config.slots) == 12

    def test_non_booking_kinds_carry_no_slots(self) -> None:
        config = normalise(
            ServiceConfig.model_validate(
                {"kind": "menu", "title": "Пекарня", "slots": ["Сегодня 10:00"]}
            )
        )
        assert config.slots == []
        assert config.cta_label == "Заказать"

    def test_slug_transliterates_russian_titles(self) -> None:
        assert slugify("Автосервис на Лесной") == "avtoservis-na-lesnoi"
        assert slugify("!!!") == "service"


# --------------------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("max_settings", "stub_generator")
class TestTheBotIsAFrontDoor:
    """The bot no longer builds anything. Whatever it is sent, it answers with the same
    message and one button into the mini app - which is where storefronts are made."""

    def test_start_gets_the_welcome_with_a_banner_and_the_app_button(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        webhook(
            client,
            {
                "update_type": "bot_started",
                "chat_id": 777001,
                "user": {"user_id": OWNER_ID, "first_name": "Иван"},
            },
        )
        (welcome,) = fake_api.messages
        assert welcome["chat_id"] == 777001
        assert welcome["html"] is True
        assert welcome["image_url"].endswith("/brand/max-welcome-v3.jpg")
        assert "AIRuntime" in welcome["text"]
        assert "приложени" in welcome["text"]
        assert "одним сообщением" not in welcome["text"]
        # One button, and it opens the owner's side of the app: no payload.
        assert fake_api.buttons(welcome) == [
            {"type": "open_app", "text": "Открыть AIRuntime", "web_app": "airuntime_bot"}
        ]
        assert fake_api.actions == [{"chat_id": 777001, "action": "mark_seen"}]
        # The dialog is remembered: it is where this person's leads will arrive.
        assert db.query(MaxOwner).one().max_chat_id == 777001

    def test_any_message_gets_the_same_welcome_and_builds_nothing(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        # The chat wizard turned "привет" into a storefront called "Ваш бизнес".
        webhook(client, _message("привет"))
        webhook(client, _message("Автосервис на Лесной, диагностика 1500"))
        assert len(fake_api.messages) == 2
        assert all("AIRuntime" in text for text in fake_api.texts)
        assert fake_api.actions == [
            {"chat_id": 777001, "action": "mark_seen"},
            {"chat_id": 777001, "action": "mark_seen"},
        ]
        assert db.query(MaxService).count() == 0

    def test_group_chats_are_left_alone(self, client: TestClient, fake_api: FakeMaxApi) -> None:
        webhook(client, _message("всем привет", chat_type="chat"))
        assert fake_api.messages == []
        assert fake_api.actions == []

    def test_messages_from_bots_are_ignored(self, client: TestClient, fake_api: FakeMaxApi) -> None:
        update = _message("эхо")
        update["message"]["sender"]["is_bot"] = True
        webhook(client, update)
        assert fake_api.messages == []
        assert fake_api.actions == []

    def test_a_start_from_a_storefront_link_opens_that_storefront(
        self, client: TestClient, fake_api: FakeMaxApi
    ) -> None:
        service = create_storefront(client)
        webhook(
            client,
            {
                "update_type": "bot_started",
                "chat_id": 777002,
                "payload": service["slug"],
                "user": {"user_id": CUSTOMER_ID},
            },
        )
        (invite,) = fake_api.messages
        assert "Автосервис на Лесной" in invite["text"]
        (button,) = fake_api.buttons(invite)
        assert button["payload"] == service["slug"]
        assert fake_api.actions == [{"chat_id": 777002, "action": "mark_seen"}]

    def test_old_buttons_are_pointed_at_the_app(
        self, client: TestClient, fake_api: FakeMaxApi
    ) -> None:
        webhook(
            client,
            {
                "update_type": "message_callback",
                "chat_id": 777003,
                "callback": {"callback_id": "cb-1", "payload": "edit:whatever"},
            },
        )
        assert fake_api.callbacks == ["Всё управление теперь в приложении"]
        assert "AIRuntime" in fake_api.texts[-1]

    def test_the_banner_is_dropped_only_when_max_refuses_it(
        self, client: TestClient, fake_api: FakeMaxApi
    ) -> None:
        fake_api.refuse_images_with = MaxApiError("MAX API 400: attachment", status=400)
        webhook(client, _message("привет"))
        (welcome,) = fake_api.messages
        assert "image_url" not in welcome

    def test_no_second_copy_after_a_timeout(self, client: TestClient, fake_api: FakeMaxApi) -> None:
        # MAX may have delivered the first one; a duplicate welcome is worse than none.
        fake_api.refuse_images_with = MaxApiError("MAX API request failed: ReadTimeout")
        webhook(client, _message("привет"))
        assert fake_api.messages == []
        # The message was still read even though we did not answer.
        assert fake_api.actions == [{"chat_id": 777001, "action": "mark_seen"}]


def _message(text: str, *, chat_type: str = "dialog") -> dict[str, Any]:
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": OWNER_ID, "first_name": "Иван"},
            "recipient": {"chat_id": 777001, "chat_type": chat_type},
            "body": {"text": text},
        },
    }


# fake_api for every test: a lead notifies the owner, and without the fake that is a real
# request to platform-api2.max.ru from the test run.
@pytest.mark.usefixtures("max_settings", "stub_generator", "fake_api")
class TestOwnerToCustomerFlow:
    def test_one_description_in_the_mini_app_produces_a_bookable_storefront(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        # The owner never wrote to the bot: the mini app is where people start now.
        service = create_storefront(client)
        assert service["status"] == "live"
        assert service["config"]["title"] == "Автосервис на Лесной"
        # The deep link is the whole distribution story.
        assert service["link"] == f"https://max.ru/airuntime_bot?startapp={service['slug']}"

        # A customer opens the storefront through that link and books.
        storefront = client.get(
            f"/api/v1/max/miniapp/service/{service['slug']}",
            headers=customer_headers(service["slug"]),
        )
        assert storefront.status_code == 200
        items = [item["title"] for item in storefront.json()["config"]["items"]]
        assert items == ["Диагностика", "Замена масла"]
        book(client, service["slug"], slot_label="Сегодня 14:00", phone="+79990001122")

        lead = db.query(MaxLead).one()
        assert lead.max_user_id == CUSTOMER_ID
        assert lead.status == "new"

        # The owner is told - by user id, since they have no dialog with the bot yet - with
        # one button that opens their leads in the app.
        (notification,) = fake_api.messages
        assert notification["user_id"] == OWNER_ID
        assert "chat_id" not in notification
        assert "Новая заявка" in notification["text"]
        assert "Диагностика · Сегодня 14:00" in notification["text"]
        assert fake_api.buttons(notification) == [
            {"type": "open_app", "text": "Открыть заявки", "web_app": "airuntime_bot"}
        ]

    def test_a_lead_goes_into_the_owners_dialog_once_the_bot_knows_it(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        webhook(client, _message("привет"))
        service = create_storefront(client)
        book(client, service["slug"])
        assert fake_api.messages[-1]["chat_id"] == 777001

    def test_what_customers_type_cannot_format_the_owners_message(
        self, client: TestClient, fake_api: FakeMaxApi
    ) -> None:
        service = create_storefront(client)
        book(client, service["slug"], customer_name="<b>Пётр</b>", comment="<a href=x>жми</a>")
        text = fake_api.messages[-1]["text"]
        assert "<b>Пётр</b>" not in text and "&lt;b&gt;Пётр&lt;/b&gt;" in text
        assert "<a href" not in text

    def test_owner_confirms_in_the_mini_app_and_customer_is_told_once(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service = create_storefront(client)
        book(client, service["slug"], slot_label="Сегодня 14:00")
        lead = db.query(MaxLead).one()

        for _ in range(2):
            response = client.post(
                f"/api/v1/max/miniapp/owner/leads/{lead.id}/status",
                json={"status": "confirmed"},
                headers=owner_headers(),
            )
            assert response.status_code == 200

        customer_messages = [m for m in fake_api.messages if m.get("user_id") == CUSTOMER_ID]
        # Sent by user id: a user id is not a chat id, and a customer who only opened the
        # mini app has no dialog with the bot. And sent once, not per tap.
        assert len(customer_messages) == 1
        assert "Запись подтверждена" in customer_messages[0]["text"]
        (button,) = fake_api.buttons(customer_messages[0])
        assert button["payload"] == service["slug"]

    def test_a_declined_customer_is_offered_another_time(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service = create_storefront(client)
        book(client, service["slug"], slot_label="Сегодня 14:00")
        lead = db.query(MaxLead).one()
        client.post(
            f"/api/v1/max/miniapp/owner/leads/{lead.id}/status",
            json={"status": "declined"},
            headers=owner_headers(),
        )
        text = fake_api.messages[-1]["text"]
        assert "Время не подошло" in text and "Сегодня 14:00" in text

    def test_edit_keeps_the_link_that_is_already_out_there(
        self, client: TestClient, db: Session
    ) -> None:
        service = create_storefront(client)
        response = client.post(
            f"/api/v1/max/miniapp/owner/services/{service['slug']}/edit",
            json={"instruction": "добавь шиномонтаж 2400"},
            headers=owner_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["changed"] is True
        assert body["slug"] == service["slug"]
        assert "Шиномонтаж" in [item["title"] for item in body["config"]["items"]]

    def test_unpublished_storefront_is_hidden_from_customers_but_not_its_owner(
        self, client: TestClient
    ) -> None:
        service = create_storefront(client)
        slug = service["slug"]
        response = client.post(
            f"/api/v1/max/miniapp/owner/services/{slug}/status",
            json={"status": "disabled"},
            headers=owner_headers(),
        )
        assert response.json()["status"] == "disabled"
        path = f"/api/v1/max/miniapp/service/{slug}"
        assert client.get(path, headers=customer_headers(slug)).status_code == 404
        assert client.get(path, headers=owner_headers()).status_code == 200

    def test_delete_takes_the_leads_with_it(self, client: TestClient, db: Session) -> None:
        service = create_storefront(client)
        book(client, service["slug"])
        response = client.delete(
            f"/api/v1/max/miniapp/owner/services/{service['slug']}", headers=owner_headers()
        )
        assert response.status_code == 204
        assert db.query(MaxService).count() == 0
        assert db.query(MaxLead).count() == 0

    def test_a_vague_brief_is_refused_rather_than_turned_into_a_storefront(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.post(
            "/api/v1/max/miniapp/owner/services", json={"brief": "привет"}, headers=owner_headers()
        )
        assert response.status_code == 422
        assert "подробнее" in response.json()["detail"]
        assert db.query(MaxService).count() == 0

    def test_the_eleventh_storefront_is_refused(self, client: TestClient) -> None:
        for _ in range(storefronts.MAX_SERVICES_PER_OWNER):
            create_storefront(client)
        response = client.post(
            "/api/v1/max/miniapp/owner/services", json={"brief": BRIEF}, headers=owner_headers()
        )
        assert response.status_code == 409


# --------------------------------------------------------------------------------------
# Authorisation and input handling
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("max_settings", "stub_generator")
class TestMiniAppAuthorisation:
    def test_api_rejects_requests_without_launch_data(self, client: TestClient) -> None:
        assert client.get("/api/v1/max/miniapp/service/anything").status_code == 401
        assert client.get("/api/v1/max/miniapp/owner/overview").status_code == 401

    def test_preflight_allows_the_init_data_header(self, client: TestClient) -> None:
        response = client.options(
            "/api/v1/max/miniapp/owner/overview",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type,x-max-init-data",
            },
        )
        assert response.status_code == 200
        allowed = {
            part.strip().lower()
            for part in response.headers.get("access-control-allow-headers", "").split(",")
        }
        assert "x-max-init-data" in allowed

    def test_api_rejects_launch_data_signed_by_another_token(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/max/miniapp/owner/overview",
            headers={"X-Max-Init-Data": build_init_data(user_id=OWNER_ID, token="forged")},
        )
        assert response.status_code == 401

    def test_lead_rejects_items_the_storefront_does_not_offer(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        slug = create_storefront(client)["slug"]
        response = client.post(
            "/api/v1/max/miniapp/lead",
            json={"slug": slug, "item_title": "Перевод 100000 рублей"},
            headers=customer_headers(slug),
        )
        # Otherwise the owner's chat becomes a place strangers can write arbitrary text into.
        assert response.status_code == 422

    def test_lead_rejects_unknown_slot(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        slug = create_storefront(client)["slug"]
        response = client.post(
            "/api/v1/max/miniapp/lead",
            json={"slug": slug, "item_title": "Диагностика", "slot_label": "Когда захочу"},
            headers=customer_headers(slug),
        )
        assert response.status_code == 422

    def test_owner_cannot_resolve_another_owners_lead(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        book(client, create_storefront(client)["slug"])
        lead = db.query(MaxLead).one()
        stranger = MaxOwner(max_user_id=999333, max_chat_id=999333)
        db.add(stranger)
        db.commit()

        response = client.post(
            f"/api/v1/max/miniapp/owner/leads/{lead.id}/status",
            json={"status": "confirmed"},
            headers=owner_headers(999333),
        )
        assert response.status_code == 404
        db.expire_all()
        assert db.query(MaxLead).one().status == "new"

    def test_owner_cannot_touch_another_owners_storefront(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        slug = create_storefront(client)["slug"]
        create_storefront(client, user_id=999444)  # the stranger has storefronts of their own
        stranger = owner_headers(999444)
        base = f"/api/v1/max/miniapp/owner/services/{slug}"
        assert client.delete(base, headers=stranger).status_code == 404
        assert (
            client.post(f"{base}/edit", json={"instruction": "всё бесплатно"}, headers=stranger)
        ).status_code == 404
        assert (
            client.post(f"{base}/status", json={"status": "disabled"}, headers=stranger)
        ).status_code == 404
        db.expire_all()
        assert db.query(MaxService).filter(MaxService.slug == slug).one().status == "live"

    def test_overview_is_empty_rather_than_failing_for_a_first_time_visitor(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/max/miniapp/owner/overview", headers=owner_headers(424242))
        assert response.status_code == 200
        assert response.json() == {"owner": None, "services": []}


# --------------------------------------------------------------------------------------
# Webhook hardening
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("max_settings")
class TestWebhookHardening:
    def test_wrong_secret_looks_like_a_missing_endpoint(self, client: TestClient) -> None:
        response = client.post("/api/v1/max/webhook/not-the-secret", json={"update_type": "ping"})
        assert response.status_code == 404

    def test_unconfigured_secret_closes_the_endpoint(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "max_webhook_secret", None)
        response = client.post(f"/api/v1/max/webhook/{WEBHOOK_SECRET}", json={"update_type": "x"})
        assert response.status_code == 404

    def test_handler_failure_still_acks(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, fake_api: FakeMaxApi
    ) -> None:
        async def explode(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(max_bot, "handle_update", explode)
        # MAX redelivers on non-2xx; a handler bug must not become a retry storm.
        response = client.post(
            f"/api/v1/max/webhook/{WEBHOOK_SECRET}", json={"update_type": "message_created"}
        )
        assert response.status_code == 200

    def test_unknown_update_types_are_ignored(
        self, client: TestClient, fake_api: FakeMaxApi
    ) -> None:
        webhook(client, {"update_type": "message_removed", "chat_id": OWNER_ID})
        assert fake_api.messages == []
