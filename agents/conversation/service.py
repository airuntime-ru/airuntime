from collections.abc import AsyncIterator, Callable

from agents.provider.base import BaseProvider


class ConversationService:
    # The model output is user-facing only.
    # In AIRuntime the website/bot is generated and deployed on the server.
    # Therefore the assistant must not refuse when the user asks to "build/run".
    _SYSTEM_PROMPT = (
        "Ты ассистент платформы AIRuntime. "
        "Пользователь может просить: 'сделай сайт/лендинг', 'запусти на домене', 'собери и задеплой'. "
        "Ты НЕ запускаешь код и НЕ управляешь доменами напрямую. "
        "Твоя задача: вежливо подтвердить выполнение и описать, что платформа приступит к сборке/деплою. "
        "Не отвечай отказом вроде 'я не могу'. Не упоминай ограничения доступа к доменам/сайтам."
    )

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
        # Ensure system prompt exists for every request.
        history = [{"role": "system", "content": self._SYSTEM_PROMPT}, *history]
        model = self._resolve_model()
        assistant_full = ""
        async for chunk in self._provider.stream(messages=history, model=model, tools=[]):
            assistant_full += chunk
            yield chunk
        self._remember(chat_id, "assistant", assistant_full)
