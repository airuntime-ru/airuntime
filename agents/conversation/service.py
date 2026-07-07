from collections.abc import AsyncIterator, Callable

from agents.provider.base import BaseProvider


class ConversationService:
    def __init__(
        self,
        *,
        provider: BaseProvider,
        recall: Callable[[str], list[dict]],
        remember: Callable[[str, str, str], None],
        resolve_model: Callable[[], str],
    ) -> None:
        self._provider = provider
        self._recall = recall
        self._remember = remember
        self._resolve_model = resolve_model

    async def stream_reply(self, *, chat_id: str, user_message: str) -> AsyncIterator[str]:
        self._remember(chat_id, "user", user_message)
        history = self._recall(chat_id)
        if not history:
            history = [{"role": "user", "content": user_message}]
        model = self._resolve_model()
        assistant_full = ""
        async for chunk in self._provider.stream(messages=history, model=model, tools=[]):
            assistant_full += chunk
            yield chunk
        self._remember(chat_id, "assistant", assistant_full)
