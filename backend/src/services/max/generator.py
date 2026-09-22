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
from src.services.file_context import ImageAttachment
from src.services.max.schema import ServiceConfig, normalise
from src.services.max.slots import fallback_slots, now_msk, russian_today
from src.services.provider.factory import resolve_provider_and_model
from src.services.system_settings import resolve_platform_api_key

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT_HINT = "Собираю сервис…"

# Three because the owner is watching a chat: at roughly five seconds a turn, two retries
# stay inside the patience the "Собираю сервис…" line buys, and a fourth would not.
_ATTEMPTS = 3


class LlmUnavailable(RuntimeError):
    """No model can be called at all. Distinct from a turn that went wrong: the caller must
    not burn the retry budget on a deployment that simply has no key."""


_SYSTEM_PROMPT = """Ты — генератор сервисов AIRuntime для мессенджера MAX.

Владелец описывает бизнес в мини-приложении. К описанию могут быть приложены сайт \
(текст страницы и цвета) и файлы: логотип, фото, прайс, референс дизайна. Твоя задача — \
превратить это в JSON-конфигурацию готового сервиса, которую клиенты откроют прямо в MAX.

Верни СТРОГО один JSON-объект без markdown, без пояснений, без ```-ограждений.

Схема:
{
  "kind": "booking" | "menu" | "landing",
  "title": "название бизнеса, до 120 символов",
  "tagline": "короткий подзаголовок, до 160 символов",
  "about": "1-3 предложения о бизнесе, до 600 символов",
  "accent": "#RRGGBB — акцентный цвет, уместный отрасли",
  "mood": "calm" | "warm" | "bold" | "minimal",
  "contacts": {"phone": "", "address": "", "hours": ""},
  "items": [
    {"title": "название позиции", "description": "короткое пояснение или пустая строка",
     "price_rub": 1500, "duration_min": 60}
  ],
  "slots": ["Вт 23 сен, 16:00", "Ср 24 сен, 18:00"],
  "cta_label": "текст кнопки действия",
  "success_message": "что увидит клиент после отправки",
  "comment_hint": "плейсхолдер поля комментария, по делу этого бизнеса",
  "ask_phone": true,
  "ask_comment": true
}

Правила:
- kind: "booking" — если клиент записывается на время (услуги, мастера, репетитор, приём); \
"menu" — если выбирает позицию из каталога или меню (еда, доставка, товары); \
"landing" — если просто оставляет заявку (консультация, презентация, сбор контактов).
- items: только то, что владелец реально назвал. Если назвал одну услугу — верни одну. \
Не размножай шаблонными «Услуга 2», «Пакет 3», «Консультация VIP». 3-8 позиций — только \
когда в описании, на сайте или в прайсе действительно столько пунктов.
- duration_min заполняй только для kind = "booking" и только если это осмысленно.
- slots: 4-6 ближайших слотов, только для kind = "booking". Формат строго \
«Вт 23 сен, 16:00» — конкретный день, без слов «сегодня» и «завтра». \
Для остальных типов — пустой массив.
- contacts: заполняй только тем, что пользователь реально написал. Не выдумывай телефон, \
адрес и часы работы — оставляй пустую строку.
- comment_hint: подсказка в поле комментария ИМЕННО для этого бизнеса. \
Репетитор — «Класс, тема занятия, онлайн или очно». Автосервис — «Марка, год, что случилось». \
Кафе — «Аллергии, пожелания к заказу». Никогда не ставь «марка авто», если это не про машины.
- mood: calm — обучение, психология, медицина, репетитор; warm — еда, дети, уют; \
bold — авто, барбер, спорт, ремонт; minimal — консультации, B2B, заявки.
- title и tagline — как вывеска, не канцелярия. Никаких «Качественные услуги», \
«Индивидуальный подход», «Профессионализм». about — 1-3 конкретных предложения: \
для кого, в каком формате, что получает клиент.
- accent: не дефолтный синий, если отрасль подсказывает другой цвет \
(репетитор — чернила/лес, кафе — терракота, барбер — графит). Если есть фото или цвета \
сайта — accent должен им соответствовать.
- Весь текст — на русском языке, деловой и короткий. Без восклицательных знаков и эмодзи.
- Никаких обещаний, гарантий, лицензий и цен, которых не было в описании, на сайте \
или в файлах владельца.
- Если есть сайт или прайс — услуги и цены бери оттуда, ничего не выдумывай.
- Фото смотри как дизайнер: характер, палитра, настроение. В JSON картинки не вставляй."""

_EDIT_SYSTEM_PROMPT = """Ты редактируешь JSON-конфигурацию сервиса AIRuntime в мессенджере MAX.

Тебе дают текущую конфигурацию и просьбу пользователя её изменить. Верни СТРОГО один \
JSON-объект той же схемы — полную обновлённую конфигурацию, без markdown и пояснений.

Меняй только то, о чём попросил пользователь. Всё остальное оставь ровно как было, \
включая формулировки, цены, mood, comment_hint и порядок позиций. Слоты, если их \
трогают, пиши в формате «Вт 23 сен, 16:00»."""


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


async def _complete(
    system_prompt: str, user_text: str, *, images: list[ImageAttachment] | None = None
) -> str:
    wire_provider, model, api_key = _resolve_llm()
    if not api_key:
        raise LlmUnavailable("No LLM provider is configured")

    provider = get_agent_provider(wire_provider)
    messages = provider.build_messages([], user_text[:8000], images=images or ())
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
_TUTOR_TERMS = ("репетитор", "урок", "егэ", "огэ", "занят", "математик", "английск", "физик")


def _fallback_mood(prompt: str, kind: str) -> str:
    lowered = (prompt or "").lower()
    if any(term in lowered for term in _TUTOR_TERMS):
        return "calm"
    if any(term in lowered for term in _MENU_TERMS):
        return "warm"
    if kind == "landing":
        return "minimal"
    return "bold"


def _fallback_config(prompt: str) -> ServiceConfig:
    """A usable draft when the model is unavailable - the wizard must never dead-end."""
    lowered = (prompt or "").lower()
    if any(term in lowered for term in _MENU_TERMS):
        kind, items = "menu", ["Позиция 1", "Позиция 2", "Позиция 3"]
    elif any(term in lowered for term in _LANDING_TERMS):
        kind, items = "landing", ["Консультация"]
    elif any(term in lowered for term in _TUTOR_TERMS):
        kind, items = "booking", ["Занятие"]
    else:
        kind, items = "booking", ["Услуга 1"]

    title = (prompt or "Мой сервис").strip().split("\n")[0][:60] or "Мой сервис"
    return normalise(
        ServiceConfig.model_validate(
            {
                "kind": kind,
                "title": title,
                "tagline": "Заполните описание в приложении",
                "about": "",
                "mood": _fallback_mood(prompt, kind),
                "items": [{"title": item} for item in items],
                "slots": fallback_slots() if kind == "booking" else [],
            }
        )
    )


async def _config_from_model(
    system_prompt: str,
    user_text: str,
    *,
    what: str,
    images: list[ImageAttachment] | None = None,
) -> ServiceConfig | None:
    """One storefront out of the model, or None once the attempts are used up.

    The retry is not politeness about a flaky network. The proxy in front of the model
    offers it a tool set we never asked for (we send no ``tools`` at all), and the model
    answers a measured one turn in three by calling ``bash`` instead of writing anything -
    a 200 with no text in it. ``tool_choice: "none"`` reduces that and does not remove it,
    so the only thing between an owner's real prices and a stub reading "Услуга 1" is
    asking again.
    """
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            raw = await _complete(system_prompt, user_text, images=images)
            return normalise(ServiceConfig.model_validate(_extract_json(raw)))
        except LlmUnavailable:
            logger.warning("%s: no model configured, not retrying", what, exc_info=True)
            return None
        except Exception:
            logger.warning("%s attempt %s/%s failed", what, attempt, _ATTEMPTS, exc_info=True)
    return None


def _dated_prompt(prompt: str) -> str:
    return (
        f"Сегодня: {russian_today(now_msk())} (Москва). "
        "Слоты пиши только конкретными днями в формате «Вт 23 сен, 16:00».\n\n"
        f"{prompt}"
    )


async def generate_config(
    prompt: str, *, images: list[ImageAttachment] | None = None
) -> tuple[ServiceConfig, bool]:
    """Return ``(config, used_llm)`` for a fresh storefront."""
    config = await _config_from_model(
        _SYSTEM_PROMPT, _dated_prompt(prompt), what="max_generate_config", images=images
    )
    if config is None:
        return _fallback_config(prompt), False
    return config, True


async def apply_edit(config: ServiceConfig, instruction: str) -> tuple[ServiceConfig, bool]:
    """Return ``(config, changed)`` after applying a free-form edit request."""
    current = json.dumps(config.model_dump(), ensure_ascii=False)
    user_text = f"Текущая конфигурация:\n{current}\n\nПросьба пользователя:\n{instruction}"
    updated = await _config_from_model(_EDIT_SYSTEM_PROMPT, user_text, what="max_apply_edit")
    if updated is None:
        return config, False
    return updated, True
