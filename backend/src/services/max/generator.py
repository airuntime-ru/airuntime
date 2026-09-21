"""One prompt in, a validated storefront out.

The owner types a sentence about their business into the MAX bot; this turns it into a
``ServiceConfig``. Two deliberate choices:

- **the model never writes code here.** It fills a schema. A storefront is then rendered by
  one multi-tenant mini app, so "describe it -> a customer can book" takes seconds and
  cannot be broken by a model that had a bad day. Code generation (the regular AIRuntime
  pipeline) stays available for the public site, where minutes are acceptable.
- **it always returns something.** If the provider is down or answers with noise, the
  keyword fallback still produces a usable draft the owner can edit in the bot. A wizard
  that dead-ends on a provider hiccup is worse than a rough first draft.
"""

from __future__ import annotations

import json
import logging
import re

from src.core.config import settings
from src.services.agent.events import TextDelta, TurnFinished
from src.services.agent.providers import get_agent_provider
from src.services.max.schema import ServiceConfig, normalise
from src.services.provider.factory import resolve_provider_and_model
from src.services.system_settings import resolve_platform_api_key

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT_HINT = "Собираю сервис…"

_SYSTEM_PROMPT = """Ты — генератор витрин для мессенджера MAX.

Пользователь одним сообщением описывает свой бизнес или идею сервиса. Твоя задача — \
превратить это описание в JSON-конфигурацию готовой витрины, которую клиенты откроют \
прямо в MAX.

Верни СТРОГО один JSON-объект без markdown, без пояснений, без ```-ограждений.

Схема:
{
  "kind": "booking" | "menu" | "landing",
  "title": "название бизнеса, до 120 символов",
  "tagline": "короткий подзаголовок, до 160 символов",
  "about": "1-3 предложения о бизнесе, до 600 символов",
  "accent": "#RRGGBB — акцентный цвет, уместный отрасли",
  "contacts": {"phone": "", "address": "", "hours": ""},
  "items": [
    {"title": "название позиции", "description": "короткое пояснение или пустая строка",
     "price_rub": 1500, "duration_min": 60}
  ],
  "slots": ["Сегодня 14:00", "Сегодня 16:00", "Завтра 10:00"],
  "cta_label": "текст кнопки действия",
  "success_message": "что увидит клиент после отправки",
  "ask_phone": true,
  "ask_comment": true
}

Правила:
- kind: "booking" — если клиент записывается на время (услуги, мастера, сервис, приём); \
"menu" — если выбирает позицию из каталога или меню (еда, доставка, товары); \
"landing" — если просто оставляет заявку (консультация, презентация, сбор контактов).
- items: 3-8 позиций. Если пользователь назвал конкретные услуги и цены — используй \
ИМЕННО их, ничего не выдумывай и не округляй. Если цен нет — ставь price_rub: null.
- duration_min заполняй только для kind = "booking" и только если это осмысленно.
- slots: 4-6 ближайших слотов простым текстом, только для kind = "booking". \
Для остальных типов — пустой массив.
- contacts: заполняй только тем, что пользователь реально написал. Не выдумывай телефон, \
адрес и часы работы — оставляй пустую строку.
- Весь текст — на русском языке, деловой и короткий. Без восклицательных знаков и эмодзи.
- Никаких обещаний, гарантий, лицензий и цен, которых не было в описании пользователя."""

_EDIT_SYSTEM_PROMPT = """Ты редактируешь JSON-конфигурацию витрины в мессенджере MAX.

Тебе дают текущую конфигурацию и просьбу пользователя её изменить. Верни СТРОГО один \
JSON-объект той же схемы — полную обновлённую конфигурацию, без markdown и пояснений.

Меняй только то, о чём попросил пользователь. Всё остальное оставь ровно как было, \
включая формулировки, цены и порядок позиций."""


def _resolve_llm() -> tuple[str, str, str]:
    """Pick the provider/model/key for a short interactive call.

    The coding agent routes "openai" through the Codex CLI container, which is the right
    trade-off for writing a repository and the wrong one for a chat wizard that has to
    answer in seconds. Here we always take the plain HTTP path, mapping "openai" onto the
    OpenAI-compatible proxy when one is configured so the key matches the endpoint.

    Swapping the endpoint means swapping the model name with it: the two speak different
    catalogues, and a Codex model id sent to the proxy comes back as HTTP 400 `Model not
    found`. That failure used to be invisible - see ``_complete``.
    """
    provider, model = resolve_provider_and_model()
    api_key = resolve_platform_api_key(provider) or ""
    wire_provider = provider
    if provider == "openai" and (settings.openai_base_url or "").strip():
        wire_provider = "routerai"
        model = (settings.max_wizard_model or "").strip() or model
    return wire_provider, model, api_key


async def _complete(system_prompt: str, user_text: str) -> str:
    wire_provider, model, api_key = _resolve_llm()
    if not api_key:
        raise RuntimeError("No LLM provider is configured")

    provider = get_agent_provider(wire_provider)
    messages = provider.build_messages([], user_text[:6000])
    collected = ""
    failure = ""
    async for event in provider.stream_turn(
        system_prompt=system_prompt,
        messages=messages,
        tools=[],
        model=model,
        api_key=api_key,
    ):
        if isinstance(event, TextDelta):
            collected += event.text
        elif isinstance(event, TurnFinished) and event.stop_reason == "error":
            failure = event.error or "provider reported an error"
    # A provider adapter reports a failed turn as an event, not an exception, so collecting
    # only TextDelta turns "the model is misconfigured" into "the model said nothing" - and
    # the caller's fallback then quietly serves "Услуга 1, Услуга 2" as if that were the
    # answer. This is the one place that can tell the difference, so it raises.
    if failure:
        raise RuntimeError(f"{wire_provider}/{model}: {failure}")
    return collected


def _extract_json(raw: str) -> dict:
    """Pull the JSON object out of a reply that may still be wrapped in prose or fences."""
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object in model reply")
        text = match.group(0)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Model reply is not a JSON object")
    return payload


_MENU_TERMS = ("меню", "кафе", "ресторан", "кофейн", "доставк", "пицц", "суши", "бар", "пекарн")
_LANDING_TERMS = ("лендинг", "landing", "заявк", "консультац", "презентац", "курс", "вебинар")


def _fallback_config(prompt: str) -> ServiceConfig:
    """A usable draft when the model is unavailable - the wizard must never dead-end."""
    lowered = (prompt or "").lower()
    if any(term in lowered for term in _MENU_TERMS):
        kind, items = "menu", ["Позиция 1", "Позиция 2", "Позиция 3"]
    elif any(term in lowered for term in _LANDING_TERMS):
        kind, items = "landing", ["Консультация"]
    else:
        kind, items = "booking", ["Услуга 1", "Услуга 2", "Услуга 3"]

    title = (prompt or "Мой сервис").strip().split("\n")[0][:60] or "Мой сервис"
    return normalise(
        ServiceConfig.model_validate(
            {
                "kind": kind,
                "title": title,
                "tagline": "Заполните описание в боте",
                "about": "",
                "items": [{"title": item} for item in items],
                "slots": (
                    ["Сегодня 12:00", "Сегодня 15:00", "Завтра 11:00", "Завтра 14:00"]
                    if kind == "booking"
                    else []
                ),
            }
        )
    )


async def generate_config(prompt: str) -> tuple[ServiceConfig, bool]:
    """Return ``(config, used_llm)`` for a fresh storefront."""
    try:
        raw = await _complete(_SYSTEM_PROMPT, prompt)
        config = ServiceConfig.model_validate(_extract_json(raw))
        return normalise(config), True
    except Exception:
        logger.warning("max_generate_config_failed", exc_info=True)
        return _fallback_config(prompt), False


async def apply_edit(config: ServiceConfig, instruction: str) -> tuple[ServiceConfig, bool]:
    """Return ``(config, changed)`` after applying a free-form edit request."""
    current = json.dumps(config.model_dump(), ensure_ascii=False)
    user_text = f"Текущая конфигурация:\n{current}\n\nПросьба пользователя:\n{instruction}"
    try:
        raw = await _complete(_EDIT_SYSTEM_PROMPT, user_text)
        updated = ServiceConfig.model_validate(_extract_json(raw))
        return normalise(updated), True
    except Exception:
        logger.warning("max_apply_edit_failed", exc_info=True)
        return config, False
