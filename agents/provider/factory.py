from agents.provider.base import BaseProvider
from agents.provider.http import HttpProvider


def get_provider(provider_name: str, api_key: str, base_url: str) -> BaseProvider:
    if provider_name in {"openai", "anthropic", "gemini", "openrouter"}:
        return HttpProvider(provider_name=provider_name, api_key=api_key, base_url=base_url)
    return HttpProvider(provider_name="openai", api_key=api_key, base_url=base_url)
