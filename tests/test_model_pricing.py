from src.services.model_pricing import (
    estimate_model_usage_cost,
    is_selectable_model,
    public_model_options,
)


def _usage() -> dict[str, int]:
    return {
        "input_tokens": 1_000,
        "cached_input_tokens": 200,
        "cache_write_input_tokens": 300,
        "output_tokens": 100,
    }


def test_openai_models_have_different_token_costs() -> None:
    sol = estimate_model_usage_cost(provider="openai", model="gpt-5.6-sol", usage=_usage())
    terra = estimate_model_usage_cost(provider="openai", model="gpt-5.6-terra", usage=_usage())
    luna = estimate_model_usage_cost(provider="openai", model="gpt-5.6-luna", usage=_usage())

    assert sol is not None and sol.credits == 75
    assert terra is not None and terra.credits == 38
    assert luna is not None and luna.credits == 15
    assert sol.provider_cost_usd_micros == 7_475


def test_cache_tokens_replace_instead_of_duplicate_input_tokens() -> None:
    cost = estimate_model_usage_cost(
        provider="openai",
        model="gpt-5.6-sol",
        usage={
            "input_tokens": 1_000,
            "cached_input_tokens": 400,
            "cache_write_input_tokens": 600,
            "output_tokens": 0,
        },
    )

    assert cost is not None
    # (400 * $0.50 + 600 * $6.25) / 1M = $0.00395 = 39.5 credits -> 40.
    assert cost.credits == 40
    assert cost.input_tokens == 1_000


def test_public_catalog_contains_three_selectable_openai_tiers() -> None:
    options = public_model_options("openai")

    assert [row["id"] for row in options] == [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]
    assert all(is_selectable_model("openai", row["id"]) for row in options)
    assert not is_selectable_model("openai", "made-up-expensive-model")
