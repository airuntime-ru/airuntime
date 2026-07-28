import pytest

from src.services.provider.factory import meets_openai_floor, resolve_provider_and_model


def test_openai_quality_floor_accepts_current_frontier_models() -> None:
    assert meets_openai_floor("gpt-5.6-sol")
    assert meets_openai_floor("gpt-5.6")
    assert meets_openai_floor("gpt-5.7")


def test_openai_quality_floor_rejects_cost_optimized_and_older_models() -> None:
    assert not meets_openai_floor("gpt-5.6-terra")
    assert not meets_openai_floor("gpt-5.6-luna")
    assert not meets_openai_floor("gpt-5.4-mini")
    assert not meets_openai_floor("gpt-5.4")


def test_explicit_selectable_model_is_preserved() -> None:
    assert resolve_provider_and_model(
        provider_override="openai", model_override="gpt-5.6-terra"
    ) == ("openai", "gpt-5.6-terra")


def test_arbitrary_client_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="not available"):
        resolve_provider_and_model(provider_override="openai", model_override="not-a-real-model")
