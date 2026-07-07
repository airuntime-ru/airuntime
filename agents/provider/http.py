from collections.abc import AsyncIterator

import httpx

from agents.provider.base import BaseProvider


class HttpProvider(BaseProvider):
    def __init__(self, provider_name: str, api_key: str, base_url: str) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url

    async def stream(
        self, *, messages: list[dict], model: str, tools: list[dict]
    ) -> AsyncIterator[str]:
        _ = tools
        if not self.api_key:
            raise RuntimeError(f"{self.provider_name} API key is missing")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages},
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            for token in text.split(" "):
                yield f"{token} "
