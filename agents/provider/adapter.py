from collections.abc import AsyncIterator

from agents.provider.base import BaseProvider


class ProviderAdapter(BaseProvider):
    """Adapts any backend provider client to the agents provider interface."""

    def __init__(self, client) -> None:
        self._client = client

    async def stream(
        self, *, messages: list[dict], model: str, tools: list[dict]
    ) -> AsyncIterator[str]:
        async for chunk in self._client.stream(messages=messages, model=model, tools=tools):
            yield chunk

    async def complete(self, *, messages: list[dict], model: str) -> str:
        chunks: list[str] = []
        async for chunk in self.stream(messages=messages, model=model, tools=[]):
            chunks.append(chunk)
        return "".join(chunks)
