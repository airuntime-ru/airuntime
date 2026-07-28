"""Selectable model catalog and immutable per-run price calculation.

Prices are provider list prices per one million tokens. The resulting credit amount is rounded
up once per task and stored in the ledger, so later FX or catalog changes never rewrite history.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any

from src.core.config import CURATED_TOP_MODELS, settings

_MILLION = Decimal(1_000_000)
_USD_MICRO = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelPrice:
    provider: str
    model: str
    label: str
    description: str
    tier: str
    input_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    # GPT-5.6 cache writes are billed at 1.25x the uncached input rate.
    cache_write_usd_per_million: Decimal


@dataclass(frozen=True)
class ModelUsageCost:
    credits: int
    provider_cost_usd_micros: int
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int

    @property
    def provider_cost_usd(self) -> Decimal:
        return Decimal(self.provider_cost_usd_micros) / _USD_MICRO


_OPENAI_PRICES = (
    ModelPrice(
        provider="openai",
        model="gpt-5.6-sol",
        label="GPT-5.6 Sol",
        description="Максимальное качество для сложной разработки",
        tier="quality",
        input_usd_per_million=Decimal("5"),
        cached_input_usd_per_million=Decimal("0.5"),
        output_usd_per_million=Decimal("30"),
        cache_write_usd_per_million=Decimal("6.25"),
    ),
    ModelPrice(
        provider="openai",
        model="gpt-5.6-terra",
        label="GPT-5.6 Terra",
        description="Баланс качества, скорости и стоимости",
        tier="balanced",
        input_usd_per_million=Decimal("2.5"),
        cached_input_usd_per_million=Decimal("0.25"),
        output_usd_per_million=Decimal("15"),
        cache_write_usd_per_million=Decimal("3.125"),
    ),
    ModelPrice(
        provider="openai",
        model="gpt-5.6-luna",
        label="GPT-5.6 Luna",
        description="Экономичный режим для простых и массовых задач",
        tier="economy",
        input_usd_per_million=Decimal("1"),
        cached_input_usd_per_million=Decimal("0.1"),
        output_usd_per_million=Decimal("6"),
        cache_write_usd_per_million=Decimal("1.25"),
    ),
)

_PRICES = {(row.provider, row.model): row for row in _OPENAI_PRICES}
_ALIASES = {("openai", "gpt-5.6"): ("openai", "gpt-5.6-sol")}


def canonical_model(provider: str, model: str) -> tuple[str, str]:
    key = (provider.strip().lower(), model.strip().lower())
    return _ALIASES.get(key, key)


def get_model_price(provider: str, model: str) -> ModelPrice | None:
    return _PRICES.get(canonical_model(provider, model))


def is_selectable_model(provider: str, model: str) -> bool:
    """Only allow public catalog/default entries, never an arbitrary client-supplied slug."""
    provider_name = provider.strip().lower()
    candidate = model.strip()
    if not candidate:
        return False
    if get_model_price(provider_name, candidate) is not None:
        return True
    return candidate in CURATED_TOP_MODELS.get(provider_name, [])


def public_model_options(provider: str) -> list[dict[str, Any]]:
    provider_name = provider.strip().lower()
    options: list[dict[str, Any]] = []
    for model in CURATED_TOP_MODELS.get(provider_name, []):
        price = get_model_price(provider_name, model)
        if price is None:
            options.append(
                {
                    "id": model,
                    "label": model,
                    "description": "",
                    "tier": "other",
                    "input_usd_per_million": None,
                    "cached_input_usd_per_million": None,
                    "output_usd_per_million": None,
                    "input_credits_per_million": None,
                    "output_credits_per_million": None,
                }
            )
            continue
        credit_factor = Decimal(settings.billing_usd_to_rub) * Decimal(
            settings.billing_credits_per_rub
        )
        options.append(
            {
                "id": price.model,
                "label": price.label,
                "description": price.description,
                "tier": price.tier,
                "input_usd_per_million": float(price.input_usd_per_million),
                "cached_input_usd_per_million": float(price.cached_input_usd_per_million),
                "output_usd_per_million": float(price.output_usd_per_million),
                "input_credits_per_million": int(price.input_usd_per_million * credit_factor),
                "output_credits_per_million": int(price.output_usd_per_million * credit_factor),
            }
        )
    return options


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return 0


def estimate_model_usage_cost(
    *,
    provider: str,
    model: str,
    usage: dict[str, Any] | None,
) -> ModelUsageCost | None:
    """Price detailed provider usage, including cache reads and writes, for a known model."""
    price = get_model_price(provider, model)
    if price is None or not usage:
        return None

    input_tokens = _usage_int(usage, "input_tokens", "prompt_tokens")
    output_tokens = _usage_int(usage, "output_tokens", "completion_tokens")
    if input_tokens <= 0 and output_tokens <= 0:
        total_tokens = _usage_int(usage, "total_tokens")
        if total_tokens <= 0:
            return None
        # Older adapters sometimes expose only total_tokens. Treating it all as input avoids
        # inventing an output ratio; current Codex events provide the detailed fields above.
        input_tokens = total_tokens

    cached_input = min(_usage_int(usage, "cached_input_tokens"), input_tokens)
    cache_write = min(
        _usage_int(usage, "cache_write_input_tokens"),
        max(0, input_tokens - cached_input),
    )
    uncached_input = max(0, input_tokens - cached_input - cache_write)

    cost_usd = (
        Decimal(uncached_input) * price.input_usd_per_million
        + Decimal(cached_input) * price.cached_input_usd_per_million
        + Decimal(cache_write) * price.cache_write_usd_per_million
        + Decimal(output_tokens) * price.output_usd_per_million
    ) / _MILLION
    credits = int(
        (
            cost_usd
            * Decimal(settings.billing_usd_to_rub)
            * Decimal(settings.billing_credits_per_rub)
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    usd_micros = int((cost_usd * _USD_MICRO).to_integral_value(rounding=ROUND_CEILING))
    return ModelUsageCost(
        credits=max(1, credits),
        provider_cost_usd_micros=max(1, usd_micros),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input,
        cache_write_input_tokens=cache_write,
        output_tokens=output_tokens,
    )
