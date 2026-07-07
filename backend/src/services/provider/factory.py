from src.core.config import settings
from src.services.provider.base import ProviderClient
from src.services.provider.external import ExternalProviderClient


def resolve_model(provider_name: str) -> str:
    mapping = {
        "openai": settings.default_model_openai,
        "anthropic": settings.default_model_anthropic,
        "gemini": settings.default_model_gemini,
        "openrouter": settings.default_model_openrouter,
    }
    return mapping.get(provider_name, settings.default_model_openai)


def get_provider(provider_name: str | None = None) -> ProviderClient:
    selected = provider_name or settings.provider_name
    if selected in {"openai", "anthropic", "gemini", "openrouter"}:
        return ExternalProviderClient(provider_name=selected)
    return ExternalProviderClient(provider_name="openai")
