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
  "layout": "classic" | "editorial" | "cards" | "poster",
  "color_scheme": "light" | "dark",
  "heading_style": "sans" | "serif" | "display",
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
- Дизайн не должен быть шаблонным. layout выбирай по задаче: classic — компактная запись; \
editorial — премиальный, спокойный или авторский бизнес; cards — меню, товары и визуальный \
каталог; poster — яркий бренд, событие, спорт, барбер, шоу. Не ставь classic по привычке.
- color_scheme и heading_style должны следовать прямому пожеланию владельца, дизайну сайта \
и референсам. Тёмную тему ставь только когда её явно просили или референс однозначно тёмный. \
Для премиального/editorial допустим serif, для poster — display, для утилитарного — sans.
- title — название вывески (бренд или как владелец назвал точку). Никогда не копируй \
служебные подписи вроде «Описание владельца», «Сайт владельца», «Название страницы».
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
- Описание владельца задаёт фокус, даже если сайт шире. Для запроса «кофейня» выбирай из \
большого ресторанного меню 6-10 релевантных кофе, напитков, выпечки и десертов; не тащи \
горячие блюда только потому, что они встретились на сайте. Аналогично для любой отдельной \
точки или категории: показывай релевантную витрину, а не случайный срез всего сайта сети.
- Фото смотри как дизайнер: характер, палитра, настроение и композиция. Поле hero_image \
не добавляй: приложение само безопасно подставит загруженное владельцем фото."""

_EDIT_SYSTEM_PROMPT = """Ты редактируешь JSON-конфигурацию сервиса AIRuntime в мессенджере MAX.

Тебе дают текущую конфигурацию и просьбу пользователя её изменить. Верни СТРОГО один \
JSON-объект той же схемы — полную обновлённую конфигурацию, без markdown и пояснений.

Меняй только то, о чём попросил пользователь. Всё остальное оставь ровно как было, \
включая формулировки, цены, mood, layout, color_scheme, heading_style, comment_hint и \
порядок позиций. Слоты, если их \
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


_MENU_TERMS = (
    "меню",
    "кафе",
    "ресторан",
    "кофейн",
    "доставк",
    "пицц",
    "суши",
    "бар",
    "пекарн",
    "кофемани",
)
_LANDING_TERMS = ("лендинг", "landing", "заявк", "консультац", "презентац", "курс", "вебинар")
_TUTOR_TERMS = ("репетитор", "урок", "егэ", "огэ", "занят", "математик", "английск", "физик")

_SKIP_TITLE_PREFIXES = (
    "описание владельца",
    "сайт владельца",
    "текст страницы",
    "цвета с сайта",
    "позиции с сайта",
    "что написал",
    "описание:",
)

_GRAY_ACCENTS = {
    "#fff",
    "#ffffff",
    "#000",
    "#000000",
    "#212121",
    "#a0a1a4",
    "#f5f5f5",
    "#f3f4f5",
    "#b0b3b6",
    "#2e7cf6",
}

_PRICED_LINE = re.compile(
    r"^\s*[-•*]?\s*(.+?)\s*[—–\-:]\s*(\d{2,7})\s*(?:₽|руб(?:\.|лей|ля)?)?\s*$",
    re.M,
)
_PRICED_INLINE = re.compile(
    r"([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9&«»\"'(). -]{1,40}?)\s+(\d{2,6})(?:\s*(?:₽|руб))?"
)


def _fallback_mood(prompt: str, kind: str) -> str:
    lowered = (prompt or "").lower()
    if any(term in lowered for term in _TUTOR_TERMS):
        return "calm"
    if any(term in lowered for term in _MENU_TERMS):
        return "warm"
    if kind == "landing":
        return "minimal"
    return "bold"


def _fallback_design(prompt: str, kind: str, mood: str) -> tuple[str, str, str]:
    lowered = (prompt or "").lower()
    scheme = (
        "dark" if re.search(r"т[её]мн(?:ая|ый|ое|ую)|dark\s*(?:mode|theme)", lowered) else "light"
    )
    if kind == "menu":
        return "cards", scheme, "serif" if mood == "warm" else "sans"
    if any(word in lowered for word in ("премиум", "люкс", "бутик", "авторск", "галере")):
        return "editorial", scheme, "serif"
    if any(word in lowered for word in ("ярк", "дерзк", "фестиваль", "концерт", "спорт", "барбер")):
        return "poster", scheme, "display"
    if mood in {"calm", "minimal"}:
        return "editorial", scheme, "serif" if mood == "calm" else "sans"
    return "classic", scheme, "sans"


def _fallback_title(prompt: str) -> str:
    brand = ""
    owner_line = ""
    page_name = ""
    for raw in (prompt or "").splitlines():
        stripped = raw.strip().strip(":")
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("бренд:"):
            brand = stripped.split(":", 1)[-1].strip()
            continue
        if lower.startswith("название страницы"):
            page_name = stripped.split(":", 1)[-1].split("—")[0].split(" - ")[0].strip()
            continue
        if any(lower.startswith(prefix) for prefix in _SKIP_TITLE_PREFIXES):
            continue
        if not owner_line:
            owner_line = stripped.split(".")[0].strip()
    title = owner_line or brand or page_name or "Мой сервис"
    if title.lower() in _SKIP_TITLE_PREFIXES or title.endswith(":"):
        title = brand or page_name or "Мой сервис"
    return title[:60]


def _fallback_accent(prompt: str) -> str | None:
    for color in re.findall(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", prompt or ""):
        if color.lower() in _GRAY_ACCENTS:
            continue
        return color
    return None


def _parse_priced_items(prompt: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()

    def add(name: str, price: int) -> None:
        title = re.sub(r"\s+", " ", name).strip(" .,;:—-–")
        if len(title) < 2 or title.lower() in seen:
            return
        if title.lower() in {"заказ", "меню", "сайт", "с", "до", "позиции с сайта"}:
            return
        if price < 40 or price > 500_000:
            return
        seen.add(title.lower())
        found.append({"title": title[:120], "price_rub": price})

    for match in _PRICED_LINE.finditer(prompt or ""):
        add(match.group(1), int(match.group(2)))
    if found:
        return found[:8]

    for match in _PRICED_INLINE.finditer(prompt or ""):
        preceding = (prompt or "")[max(0, match.start() - 3) : match.start()].lower()
        if preceding.endswith("с ") or preceding.endswith("до "):
            continue
        add(match.group(1), int(match.group(2)))
    return found[:8]


def _fallback_config(prompt: str) -> ServiceConfig:
    """A usable draft when the model is unavailable - the wizard must never dead-end."""
    lowered = (prompt or "").lower()
    priced = _parse_priced_items(prompt)
    if any(term in lowered for term in _MENU_TERMS):
        kind = "menu"
        items = priced or [{"title": "Кофе"}, {"title": "Выпечка"}]
    elif any(term in lowered for term in _LANDING_TERMS):
        kind = "landing"
        items = priced or [{"title": "Консультация"}]
    elif any(term in lowered for term in _TUTOR_TERMS):
        kind = "booking"
        items = priced or [{"title": "Занятие"}]
    else:
        kind = "booking"
        items = priced or [{"title": "Услуга"}]

    title = _fallback_title(prompt)
    tagline = ""
    for raw in (prompt or "").splitlines():
        stripped = raw.strip()
        if stripped.lower().startswith("описание:") and "заполните" not in stripped.lower():
            tagline = stripped.split(":", 1)[-1].strip()[:160]
            break
    mood = _fallback_mood(prompt, kind)
    layout, color_scheme, heading_style = _fallback_design(prompt, kind, mood)
    payload: dict[str, object] = {
        "kind": kind,
        "title": title,
        "tagline": tagline,
        "about": "",
        "mood": mood,
        "layout": layout,
        "color_scheme": color_scheme,
        "heading_style": heading_style,
        "items": items,
        "slots": fallback_slots() if kind == "booking" else [],
    }
    accent = _fallback_accent(prompt)
    if accent:
        payload["accent"] = accent
    return normalise(ServiceConfig.model_validate(payload))


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
    # Inline images can be close to a megabyte. Sending one back to the text model would
    # consume the whole prompt window and truncate the owner's actual edit instruction.
    # It is immutable application data, so keep it out of the turn and restore it after.
    current = json.dumps(config.model_dump(exclude={"hero_image"}), ensure_ascii=False)
    user_text = f"Текущая конфигурация:\n{current}\n\nПросьба пользователя:\n{instruction}"
    updated = await _config_from_model(_EDIT_SYSTEM_PROMPT, user_text, what="max_apply_edit")
    if updated is None:
        return config, False
    return updated.model_copy(update={"hero_image": config.hero_image}), True
