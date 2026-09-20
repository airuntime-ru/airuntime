"""The storefront contract.

Everything the mini app renders for one tenant comes from a ``ServiceConfig``. The LLM
writes it, this module is the only thing that decides whether what it wrote is usable,
and the mini app never sees an unvalidated payload.

Keeping the whole storefront as validated data (instead of generated code) is what makes
"one prompt -> a working service" take seconds and survive a bad model day: a malformed
field is clamped or dropped here, not shipped to a customer.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

# Three storefront shapes cover the services micro-business actually asks for. They differ
# in wording and in whether a time slot is part of the request, not in structure.
SERVICE_KINDS = ("booking", "menu", "landing")

MAX_ITEMS = 24
MAX_SLOTS = 12

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Cyrillic -> latin, so a Russian business name still produces a readable deep link.
_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def slugify(value: str, *, fallback: str = "service") -> str:
    """A short, URL-safe, latin slug - it ends up in ``?startapp=<slug>``."""
    lowered = unicodedata.normalize("NFKC", value or "").strip().lower()
    latin = "".join(_TRANSLIT.get(char, char) for char in lowered)
    cleaned = _SLUG_RE.sub("-", latin).strip("-")
    return (cleaned or fallback)[:40].strip("-") or fallback


class ServiceItem(BaseModel):
    """One bookable service, menu position or offer."""

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=280)
    # Kept as an integer number of roubles: the storefronts here never need kopecks, and a
    # float would only invite rounding noise in the customer-visible price.
    price_rub: int | None = Field(default=None, ge=0, le=10_000_000)
    duration_min: int | None = Field(default=None, ge=5, le=600)

    @field_validator("title", "description", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        return str(value or "").strip()


class ServiceContacts(BaseModel):
    phone: str = Field(default="", max_length=32)
    address: str = Field(default="", max_length=200)
    hours: str = Field(default="", max_length=120)

    @field_validator("phone", "address", "hours", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        return str(value or "").strip()


class ServiceConfig(BaseModel):
    """The full storefront. One row of ``max_services.config_json``."""

    kind: str = "booking"
    title: str = Field(min_length=1, max_length=120)
    tagline: str = Field(default="", max_length=160)
    about: str = Field(default="", max_length=600)
    accent: str = "#2E7CF6"
    contacts: ServiceContacts = Field(default_factory=ServiceContacts)
    items: list[ServiceItem] = Field(default_factory=list)
    # Human-readable slots ("Сегодня 14:00"). A real calendar is deliberately out of MVP
    # scope: the owner confirms in the bot, which is how a one-person business works anyway.
    slots: list[str] = Field(default_factory=list)
    # Blank by default on purpose: normalise() fills the wording that fits the kind, and a
    # non-empty default here would silently win over it ("Записаться" on a menu).
    cta_label: str = Field(default="", max_length=40)
    success_message: str = Field(default="", max_length=160)
    ask_phone: bool = True
    ask_comment: bool = True

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: object) -> str:
        kind = str(value or "").strip().lower()
        return kind if kind in SERVICE_KINDS else "booking"

    @field_validator("title", "tagline", "about", "cta_label", "success_message", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("accent", mode="before")
    @classmethod
    def _accent(cls, value: object) -> str:
        colour = str(value or "").strip()
        return colour if _HEX_COLOR_RE.match(colour) else "#2E7CF6"

    @field_validator("items", mode="after")
    @classmethod
    def _cap_items(cls, value: list[ServiceItem]) -> list[ServiceItem]:
        return value[:MAX_ITEMS]

    @field_validator("slots", mode="before")
    @classmethod
    def _slots(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = [str(slot).strip()[:64] for slot in value if str(slot or "").strip()]
        return cleaned[:MAX_SLOTS]


DEFAULT_CTA_BY_KIND = {
    "booking": "Записаться",
    "menu": "Заказать",
    "landing": "Оставить заявку",
}

DEFAULT_SUCCESS_BY_KIND = {
    "booking": "Заявка на запись принята — свяжемся для подтверждения",
    "menu": "Заказ принят — свяжемся для подтверждения",
    "landing": "Заявка принята — свяжемся с вами",
}


def normalise(config: ServiceConfig) -> ServiceConfig:
    """Fill the per-kind wording the model left blank.

    Doing it after validation rather than in the prompt keeps the storefront usable even
    when the model ignores half the instructions.
    """
    data = config.model_dump()
    if not data["cta_label"]:
        data["cta_label"] = DEFAULT_CTA_BY_KIND.get(config.kind, "Отправить")
    if not data["success_message"]:
        data["success_message"] = DEFAULT_SUCCESS_BY_KIND.get(config.kind, "Заявка принята")
    if config.kind != "booking":
        # Only a booking asks "when" - a menu order or an enquiry has no slot.
        data["slots"] = []
    return ServiceConfig.model_validate(data)
