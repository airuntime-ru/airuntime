"""The MAX bot: the owner's whole product surface.

One bot, two audiences, which is what the platform expects (a mini app must hang off a
bot, not live beside it):

- the **owner** describes a business in one message and gets a working storefront plus a
  deep link; edits, publishing and incoming leads all happen in this chat;
- the **customer** never talks to the bot in words - they arrive through
  ``?startapp=<slug>`` and the bot opens the mini app for them.

Handlers here are synchronous against the DB and ``await`` only the model call, matching
how the rest of the backend is written. Everything is fail-soft: MAX retries webhook
deliveries, so raising here would just multiply the load.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.max_platform import (
    DIALOG_AWAITING_BRIEF,
    DIALOG_AWAITING_EDIT,
    DIALOG_IDLE,
    LEAD_CONFIRMED,
    LEAD_DECLINED,
    SERVICE_DISABLED,
    SERVICE_LIVE,
    MaxLead,
    MaxOwner,
    MaxService,
)
from src.services.max.client import (
    MaxBotClient,
    button_callback,
    button_open_app,
)
from src.services.max.generator import apply_edit, generate_config
from src.services.max.schema import ServiceConfig, slugify

logger = logging.getLogger(__name__)

MAX_SERVICES_PER_OWNER = 10

BOT_COMMANDS = [
    {"name": "start", "description": "Создать сервис в MAX"},
    {"name": "services", "description": "Мои сервисы и ссылки"},
    {"name": "leads", "description": "Заявки от клиентов"},
    {"name": "help", "description": "Как это работает"},
]

WELCOME = (
    "Опишите свой бизнес одним сообщением — я соберу витрину прямо в MAX.\n\n"
    "Клиенты откроют её по ссылке и оставят заявку, а заявка придёт сюда, в этот чат.\n\n"
    "Например:\n"
    "«Автосервис на Лесной. Диагностика 1500, замена масла 900, шиномонтаж 2400. "
    "Работаем с 9 до 20»"
)

HELP = (
    "Как это работает\n\n"
    "1. Вы описываете бизнес обычными словами — одним сообщением.\n"
    "2. Я собираю витрину: услуги, цены, время, кнопку записи.\n"
    "3. Вы получаете ссылку вида max.ru/бот?startapp=… — её можно отправить клиентам "
    "или повесить QR-кодом.\n"
    "4. Клиент открывает витрину внутри MAX и записывается в два касания.\n"
    "5. Заявка приходит вам в этот чат — подтверждаете одной кнопкой.\n\n"
    "Команды: /start — новый сервис, /services — мои сервисы, /leads — заявки."
)


def get_client() -> MaxBotClient:
    return MaxBotClient(
        settings.max_bot_token or "",
        base_url=settings.max_api_base_url,
        ca_bundle=settings.max_ca_bundle,
    )


# --------------------------------------------------------------------------------------
# Owner + service helpers
# --------------------------------------------------------------------------------------


def ensure_owner(db: Session, *, user: dict[str, Any], chat_id: int | None) -> MaxOwner:
    max_user_id = int(user.get("user_id") or user.get("id") or 0)
    owner = db.query(MaxOwner).filter(MaxOwner.max_user_id == max_user_id).first()
    if owner is None:
        owner = MaxOwner(max_user_id=max_user_id)
        db.add(owner)

    first = str(user.get("first_name") or user.get("name") or "").strip()
    last = str(user.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        owner.name = name[:255]
    username = str(user.get("username") or "").strip()
    if username:
        owner.username = username[:255]
    if chat_id:
        owner.max_chat_id = chat_id
    db.flush()
    return owner


def _set_state(owner: MaxOwner, state: str, context: dict | None = None) -> None:
    owner.dialog_state = state
    owner.dialog_context_json = json.dumps(context, ensure_ascii=False) if context else None


def _context(owner: MaxOwner) -> dict:
    if not owner.dialog_context_json:
        return {}
    try:
        parsed = json.loads(owner.dialog_context_json)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def unique_slug(db: Session, title: str) -> str:
    base = slugify(title)
    candidate = base
    # Four hex characters is enough to disambiguate within one owner's handful of services
    # while keeping the deep link short enough to read off a printed QR code.
    while db.query(MaxService).filter(MaxService.slug == candidate).first() is not None:
        candidate = f"{base[:34]}-{secrets.token_hex(2)}"
    return candidate


def load_config(service: MaxService) -> ServiceConfig:
    return ServiceConfig.model_validate(json.loads(service.config_json))


def store_config(service: MaxService, config: ServiceConfig) -> None:
    service.config_json = json.dumps(config.model_dump(), ensure_ascii=False)
    service.title = config.title[:255]
    service.kind = config.kind


def service_link(service: MaxService) -> str:
    return settings.build_max_service_link(service.slug)


def _miniapp_url(path: str = "") -> str:
    return f"{settings.resolved_max_miniapp_url}{path}"


def _service_card(service: MaxService, config: ServiceConfig) -> str:
    link = service_link(service)
    lines = [
        f"{config.title}",
        config.tagline or "",
        "",
        f"Позиций: {len(config.items)}",
    ]
    if config.slots:
        lines.append(f"Слотов: {len(config.slots)}")
    lines.append("Статус: " + ("опубликован" if service.status == SERVICE_LIVE else "черновик"))
    if link:
        lines += ["", "Ссылка для клиентов:", link]
    return "\n".join(line for line in lines if line is not None).strip()


def _service_buttons(service: MaxService) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = [
        [button_open_app("Открыть витрину", _miniapp_url(f"?startapp={service.slug}"))],
        [
            button_callback("Изменить", f"edit:{service.id}"),
            button_callback(
                "Снять с публикации" if service.status == SERVICE_LIVE else "Опубликовать",
                f"toggle:{service.id}",
            ),
        ],
        [button_open_app("Заявки", _miniapp_url("?owner=1"))],
    ]
    return rows


# --------------------------------------------------------------------------------------
# Lead delivery
# --------------------------------------------------------------------------------------


def notify_owner_of_lead(db: Session, lead: MaxLead) -> None:
    """Push a new lead into the owner's MAX chat - the moment the product pays off."""
    service = db.query(MaxService).filter(MaxService.id == lead.service_id).first()
    if service is None:
        return
    owner = db.query(MaxOwner).filter(MaxOwner.id == service.owner_id).first()
    if owner is None or not owner.max_chat_id:
        return

    lines = [f"Новая заявка — {service.title}", ""]
    if lead.item_title:
        lines.append(f"Услуга: {lead.item_title}")
    if lead.slot_label:
        lines.append(f"Время: {lead.slot_label}")
    lines.append(f"Клиент: {lead.customer_name or 'без имени'}")
    if lead.phone:
        lines.append(f"Телефон: {lead.phone}")
    if lead.comment:
        lines.append(f"Комментарий: {lead.comment}")

    get_client().try_send_message(
        chat_id=owner.max_chat_id,
        text="\n".join(lines),
        buttons=[
            [
                button_callback("Подтвердить", f"lead_ok:{lead.id}"),
                button_callback("Отклонить", f"lead_no:{lead.id}"),
            ]
        ],
    )


# --------------------------------------------------------------------------------------
# Update handling
# --------------------------------------------------------------------------------------


async def handle_update(db: Session, update: dict[str, Any]) -> None:
    update_type = str(update.get("update_type") or "")
    if update_type in ("bot_started", "bot_added"):
        await _handle_started(db, update)
    elif update_type == "message_created":
        await _handle_message(db, update)
    elif update_type == "message_callback":
        await _handle_callback(db, update)
    else:
        logger.debug("max_update_ignored type=%s", update_type)


async def _handle_started(db: Session, update: dict[str, Any]) -> None:
    chat_id = _chat_id(update)
    user = update.get("user") or {}
    owner = ensure_owner(db, user=user, chat_id=chat_id)
    _set_state(owner, DIALOG_AWAITING_BRIEF)
    db.commit()

    # A start payload is how a customer arrives: max.ru/<bot>?startapp=<slug> hands the
    # slug through here, so we open their storefront instead of the owner wizard.
    payload = str(update.get("payload") or "").strip()
    if payload:
        service = db.query(MaxService).filter(MaxService.slug == payload).first()
        if service is not None and chat_id:
            config = load_config(service)
            get_client().try_send_message(
                chat_id=chat_id,
                text=f"{config.title}\n{config.tagline}".strip(),
                buttons=[
                    [button_open_app(config.cta_label, _miniapp_url(f"?startapp={service.slug}"))]
                ],
            )
            return

    if chat_id:
        get_client().try_send_message(chat_id=chat_id, text=WELCOME)


async def _handle_message(db: Session, update: dict[str, Any]) -> None:
    message = update.get("message") or {}
    body = message.get("body") or {}
    text = str(body.get("text") or "").strip()
    sender = (message.get("sender") or {}) or (update.get("user") or {})
    chat_id = _chat_id(update)
    if not chat_id:
        return

    owner = ensure_owner(db, user=sender, chat_id=chat_id)
    client = get_client()

    if text.startswith("/"):
        db.commit()
        await _handle_command(db, owner, chat_id, text)
        return

    if not text:
        db.commit()
        client.try_send_message(chat_id=chat_id, text="Опишите сервис текстом — одним сообщением.")
        return

    state = owner.dialog_state
    if state == DIALOG_AWAITING_EDIT:
        await _apply_edit_flow(db, owner, chat_id, text)
        return

    # Any free-form message that is not an edit is treated as a brief. Asking the owner to
    # press "create" first would add a step to the one thing the product promises.
    await _create_flow(db, owner, chat_id, text)


async def _handle_command(db: Session, owner: MaxOwner, chat_id: int, text: str) -> None:
    client = get_client()
    command = text.split()[0].lstrip("/").lower()

    if command == "help":
        client.try_send_message(chat_id=chat_id, text=HELP)
        return
    if command == "services":
        _send_services(db, owner, chat_id)
        return
    if command == "leads":
        client.try_send_message(
            chat_id=chat_id,
            text="Заявки открываются в мини-приложении.",
            buttons=[[button_open_app("Открыть заявки", _miniapp_url("?owner=1"))]],
        )
        return

    # /start and anything unknown put the owner back at the top of the wizard.
    _set_state(owner, DIALOG_AWAITING_BRIEF)
    db.commit()
    client.try_send_message(chat_id=chat_id, text=WELCOME)


def _send_services(db: Session, owner: MaxOwner, chat_id: int) -> None:
    client = get_client()
    services = (
        db.query(MaxService)
        .filter(MaxService.owner_id == owner.id)
        .order_by(MaxService.created_at.desc())
        .all()
    )
    if not services:
        client.try_send_message(
            chat_id=chat_id, text="Пока ни одного сервиса. Опишите бизнес одним сообщением."
        )
        return
    for service in services[:MAX_SERVICES_PER_OWNER]:
        client.try_send_message(
            chat_id=chat_id,
            text=_service_card(service, load_config(service)),
            buttons=_service_buttons(service),
        )


async def _create_flow(db: Session, owner: MaxOwner, chat_id: int, prompt: str) -> None:
    client = get_client()
    existing = db.query(MaxService).filter(MaxService.owner_id == owner.id).count()
    if existing >= MAX_SERVICES_PER_OWNER:
        db.commit()
        client.try_send_message(
            chat_id=chat_id,
            text=(
                f"Достигнут лимит в {MAX_SERVICES_PER_OWNER} сервисов. "
                "Удалите ненужный в мини-приложении, чтобы создать новый."
            ),
        )
        return

    client.try_send_message(chat_id=chat_id, text="Собираю витрину, это займёт несколько секунд…")
    config, used_llm = await generate_config(prompt)

    service = MaxService(
        owner_id=owner.id,
        slug=unique_slug(db, config.title),
        kind=config.kind,
        title=config.title[:255],
        status=SERVICE_LIVE,
        config_json="{}",
        prompt=prompt[:4000],
    )
    store_config(service, config)
    db.add(service)
    _set_state(owner, DIALOG_IDLE)
    db.commit()

    prefix = "" if used_llm else "Черновик собран без модели — проверьте и поправьте текстом.\n\n"
    client.try_send_message(
        chat_id=chat_id,
        text=prefix + _service_card(service, config),
        buttons=_service_buttons(service),
    )


async def _apply_edit_flow(db: Session, owner: MaxOwner, chat_id: int, instruction: str) -> None:
    client = get_client()
    context = _context(owner)
    service = None
    raw_id = context.get("service_id")
    if raw_id:
        try:
            service = (
                db.query(MaxService)
                .filter(MaxService.id == uuid.UUID(str(raw_id)), MaxService.owner_id == owner.id)
                .first()
            )
        except ValueError:
            service = None

    if service is None:
        _set_state(owner, DIALOG_IDLE)
        db.commit()
        client.try_send_message(chat_id=chat_id, text="Сервис не найден. Откройте /services.")
        return

    client.try_send_message(chat_id=chat_id, text="Обновляю…")
    updated, changed = await apply_edit(load_config(service), instruction)
    if changed:
        store_config(service, updated)
    _set_state(owner, DIALOG_IDLE)
    db.commit()

    prefix = "" if changed else "Не удалось применить правку, конфигурация осталась прежней.\n\n"
    client.try_send_message(
        chat_id=chat_id,
        text=prefix + _service_card(service, updated),
        buttons=_service_buttons(service),
    )


async def _handle_callback(db: Session, update: dict[str, Any]) -> None:
    callback = update.get("callback") or {}
    payload = str(callback.get("payload") or "")
    callback_id = str(callback.get("callback_id") or "")
    sender = callback.get("user") or update.get("user") or {}
    chat_id = _chat_id(update)
    client = get_client()

    owner = ensure_owner(db, user=sender, chat_id=chat_id)
    action, _, raw_id = payload.partition(":")

    if action in ("lead_ok", "lead_no"):
        _resolve_lead(db, owner, raw_id, confirmed=action == "lead_ok")
        db.commit()
        client.answer_callback(
            callback_id,
            notification="Заявка подтверждена" if action == "lead_ok" else "Заявка отклонена",
        )
        return

    service = None
    try:
        service = (
            db.query(MaxService)
            .filter(MaxService.id == uuid.UUID(raw_id), MaxService.owner_id == owner.id)
            .first()
        )
    except ValueError:
        service = None
    if service is None:
        db.commit()
        client.answer_callback(callback_id, notification="Сервис не найден")
        return

    if action == "edit":
        _set_state(owner, DIALOG_AWAITING_EDIT, {"service_id": str(service.id)})
        db.commit()
        client.answer_callback(callback_id)
        if chat_id:
            client.try_send_message(
                chat_id=chat_id,
                text=(
                    "Напишите, что поменять. Например: «добавь услугу развал-схождение 3000» "
                    "или «убери слоты на завтра»."
                ),
            )
        return

    if action == "toggle":
        service.status = SERVICE_DISABLED if service.status == SERVICE_LIVE else SERVICE_LIVE
        db.commit()
        client.answer_callback(
            callback_id,
            notification=(
                "Опубликовано" if service.status == SERVICE_LIVE else "Снято с публикации"
            ),
        )
        if chat_id:
            client.try_send_message(
                chat_id=chat_id,
                text=_service_card(service, load_config(service)),
                buttons=_service_buttons(service),
            )
        return

    db.commit()
    client.answer_callback(callback_id)


def _resolve_lead(db: Session, owner: MaxOwner, raw_id: str, *, confirmed: bool) -> None:
    try:
        lead_id = uuid.UUID(raw_id)
    except ValueError:
        return
    lead = (
        db.query(MaxLead)
        .join(MaxService, MaxService.id == MaxLead.service_id)
        .filter(MaxLead.id == lead_id, MaxService.owner_id == owner.id)
        .first()
    )
    if lead is None:
        return
    lead.status = LEAD_CONFIRMED if confirmed else LEAD_DECLINED

    # Close the loop for the customer: they booked inside MAX, so the answer belongs there
    # too rather than in an email they will not read.
    if lead.max_user_id:
        service = db.query(MaxService).filter(MaxService.id == lead.service_id).first()
        title = service.title if service else "заявка"
        text = (
            f"{title}: запись подтверждена"
            if confirmed
            else f"{title}: к сожалению, время не подошло — свяжитесь для другого варианта"
        )
        get_client().try_send_message(chat_id=lead.max_user_id, text=text)


def _chat_id(update: dict[str, Any]) -> int | None:
    raw = update.get("chat_id")
    if raw is None:
        message = update.get("message") or {}
        recipient = message.get("recipient") or {}
        raw = recipient.get("chat_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
