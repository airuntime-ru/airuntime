from collections.abc import AsyncIterator

from src.services.prompt_guard import redact_secrets, sanitize_user_message
from src.services.runtime.engine import get_runtime_engine


class ConversationService:
    async def stream_reply(self, *, chat_id: str, user_message: str) -> AsyncIterator[str]:
        safe_message = sanitize_user_message(user_message)
        engine = get_runtime_engine()
        try:
            async for chunk in engine.stream_reply(chat_id=chat_id, user_message=safe_message):
                yield chunk
        except Exception as exc:
            msg = redact_secrets(str(exc))
            lowered = msg.lower()
            if "api key" in lowered or "key is not configured" in lowered:
                yield (
                    "AI-провайдер не настроен (нет API ключа). "
                    "Но AIRuntime всё равно сгенерирует проект по вашему описанию и отправит деплой."
                )
            else:
                yield f"Runtime error: {msg}"
