"""MAX surface: launch-data verification, storefront generation and the end-to-end flow.

The happy path is deliberately exercised through the real HTTP endpoints with a fake MAX
API, because the thing worth protecting is the whole chain - owner writes one message,
storefront exists, customer books, owner gets it in chat - not any single function.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.max_platform import MaxLead, MaxOwner, MaxService
from src.services.max import bot as max_bot
from src.services.max.client import MaxBotClient
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

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        outer = self

        def send_message(
            self: MaxBotClient,
            *,
            chat_id: int,
            text: str,
            buttons: list[list[dict[str, Any]]] | None = None,
        ) -> None:
            outer.messages.append({"chat_id": chat_id, "text": text, "buttons": buttons or []})

        def answer_callback(
            self: MaxBotClient, callback_id: str, *, notification: str = ""
        ) -> None:
            outer.callbacks.append(notification)

        monkeypatch.setattr(MaxBotClient, "send_message", send_message)
        monkeypatch.setattr(MaxBotClient, "answer_callback", answer_callback)

    @property
    def texts(self) -> list[str]:
        return [message["text"] for message in self.messages]

    def button_payloads(self) -> list[str]:
        payloads: list[str] = []
        for message in self.messages:
            for row in message["buttons"]:
                for button in row:
                    if button.get("type") == "callback":
                        payloads.append(str(button.get("payload")))
        return payloads


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

    monkeypatch.setattr(max_bot, "generate_config", generate_config)
    monkeypatch.setattr(max_bot, "apply_edit", apply_edit)


def webhook(client: TestClient, update: dict[str, Any]) -> None:
    response = client.post(f"/api/v1/max/webhook/{WEBHOOK_SECRET}", json=update)
    assert response.status_code == 200


def owner_headers(user_id: int = OWNER_ID) -> dict[str, str]:
    return {"X-Max-Init-Data": build_init_data(user_id=user_id)}


def customer_headers(slug: str, user_id: int = CUSTOMER_ID) -> dict[str, str]:
    return {"X-Max-Init-Data": build_init_data(user_id=user_id, start_param=slug)}


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
class TestOwnerToCustomerFlow:
    def test_one_message_produces_a_bookable_storefront(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        webhook(
            client,
            {
                "update_type": "bot_started",
                "chat_id": OWNER_ID,
                "user": {"user_id": OWNER_ID, "first_name": "Иван"},
            },
        )
        assert "Опишите свой бизнес" in fake_api.texts[0]

        webhook(
            client,
            {
                "update_type": "message_created",
                "chat_id": OWNER_ID,
                "message": {
                    "sender": {"user_id": OWNER_ID, "first_name": "Иван"},
                    "recipient": {"chat_id": OWNER_ID},
                    "body": {"text": "Автосервис на Лесной, диагностика 1500, масло 900"},
                },
            },
        )

        service = db.query(MaxService).filter(MaxService.slug.isnot(None)).one()
        assert service.title == "Автосервис на Лесной"
        assert service.status == "live"
        # The deep link is the whole distribution story - it must be in the owner's chat.
        assert f"https://max.ru/airuntime_bot?startapp={service.slug}" in "\n".join(fake_api.texts)

        # A customer opens the storefront through that link.
        storefront = client.get(
            f"/api/v1/max/miniapp/service/{service.slug}",
            headers=customer_headers(service.slug),
        )
        assert storefront.status_code == 200
        config = storefront.json()["config"]
        assert [item["title"] for item in config["items"]] == ["Диагностика", "Замена масла"]

        created = client.post(
            "/api/v1/max/miniapp/lead",
            json={
                "slug": service.slug,
                "item_title": "Диагностика",
                "slot_label": "Сегодня 14:00",
                "customer_name": "Пётр",
                "phone": "+79990001122",
                "comment": "Mazda 6",
            },
            headers=customer_headers(service.slug),
        )
        assert created.status_code == 201

        lead = db.query(MaxLead).one()
        assert lead.max_user_id == CUSTOMER_ID
        assert lead.status == "new"

        # ...and it lands in the owner's MAX chat with one-tap resolution.
        notification = fake_api.messages[-1]
        assert notification["chat_id"] == OWNER_ID
        assert "Новая заявка" in notification["text"]
        assert "Диагностика" in notification["text"]
        assert f"lead_ok:{lead.id}" in fake_api.button_payloads()

    def test_owner_confirms_lead_and_customer_is_told(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service, lead = self._service_with_lead(client, db)

        webhook(
            client,
            {
                "update_type": "message_callback",
                "chat_id": OWNER_ID,
                "callback": {
                    "callback_id": "cb-1",
                    "payload": f"lead_ok:{lead.id}",
                    "user": {"user_id": OWNER_ID},
                },
            },
        )

        db.expire_all()
        assert db.query(MaxLead).one().status == "confirmed"
        assert fake_api.callbacks[-1] == "Заявка подтверждена"
        # The customer booked inside MAX, so the answer belongs there too.
        customer_message = fake_api.messages[-1]
        assert customer_message["chat_id"] == CUSTOMER_ID
        assert "подтверждена" in customer_message["text"]

    def test_edit_applies_to_the_owners_own_service(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service = self._service(client, db)

        webhook(
            client,
            {
                "update_type": "message_callback",
                "chat_id": OWNER_ID,
                "callback": {
                    "callback_id": "cb-2",
                    "payload": f"edit:{service.id}",
                    "user": {"user_id": OWNER_ID},
                },
            },
        )
        webhook(
            client,
            {
                "update_type": "message_created",
                "chat_id": OWNER_ID,
                "message": {
                    "sender": {"user_id": OWNER_ID},
                    "recipient": {"chat_id": OWNER_ID},
                    "body": {"text": "добавь шиномонтаж 2400"},
                },
            },
        )

        db.expire_all()
        updated = json.loads(db.query(MaxService).one().config_json)
        assert "Шиномонтаж" in [item["title"] for item in updated["items"]]

    def _service(self, client: TestClient, db: Session) -> MaxService:
        webhook(
            client,
            {
                "update_type": "message_created",
                "chat_id": OWNER_ID,
                "message": {
                    "sender": {"user_id": OWNER_ID, "first_name": "Иван"},
                    "recipient": {"chat_id": OWNER_ID},
                    "body": {"text": "Автосервис на Лесной"},
                },
            },
        )
        return db.query(MaxService).one()

    def _service_with_lead(self, client: TestClient, db: Session) -> tuple[MaxService, MaxLead]:
        service = self._service(client, db)
        client.post(
            "/api/v1/max/miniapp/lead",
            json={"slug": service.slug, "item_title": "Диагностика", "customer_name": "Пётр"},
            headers=customer_headers(service.slug),
        )
        return service, db.query(MaxLead).one()


# --------------------------------------------------------------------------------------
# Authorisation and input handling
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("max_settings", "stub_generator")
class TestMiniAppAuthorisation:
    def test_api_rejects_requests_without_launch_data(self, client: TestClient) -> None:
        assert client.get("/api/v1/max/miniapp/service/anything").status_code == 401
        assert client.get("/api/v1/max/miniapp/owner/overview").status_code == 401

    def test_api_rejects_launch_data_signed_by_another_token(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/max/miniapp/owner/overview",
            headers={"X-Max-Init-Data": build_init_data(user_id=OWNER_ID, token="forged")},
        )
        assert response.status_code == 401

    def test_lead_rejects_items_the_storefront_does_not_offer(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service = TestOwnerToCustomerFlow()._service(client, db)
        response = client.post(
            "/api/v1/max/miniapp/lead",
            json={"slug": service.slug, "item_title": "Перевод 100000 рублей"},
            headers=customer_headers(service.slug),
        )
        # Otherwise the owner's chat becomes a place strangers can write arbitrary text into.
        assert response.status_code == 422

    def test_lead_rejects_unknown_slot(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        service = TestOwnerToCustomerFlow()._service(client, db)
        response = client.post(
            "/api/v1/max/miniapp/lead",
            json={
                "slug": service.slug,
                "item_title": "Диагностика",
                "slot_label": "Когда захочу",
            },
            headers=customer_headers(service.slug),
        )
        assert response.status_code == 422

    def test_owner_cannot_resolve_another_owners_lead(
        self, client: TestClient, db: Session, fake_api: FakeMaxApi
    ) -> None:
        _, lead = TestOwnerToCustomerFlow()._service_with_lead(client, db)
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
