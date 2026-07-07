import json
from redis import Redis
from redis.exceptions import RedisError

from src.core.config import settings


class RedisMemoryStore:
    def __init__(self) -> None:
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)

    def remember(self, *, chat_id: str, role: str, content: str) -> None:
        entry = json.dumps({"role": role, "content": content})
        self._redis.rpush(f"chat-memory:{chat_id}", entry)
        self._redis.ltrim(f"chat-memory:{chat_id}", -100, -1)

    def recall(self, *, chat_id: str) -> list[dict]:
        rows = self._redis.lrange(f"chat-memory:{chat_id}", 0, -1)
        return [json.loads(row) for row in rows]


class InMemoryStoreFallback:
    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    def remember(self, *, chat_id: str, role: str, content: str) -> None:
        self._store.setdefault(chat_id, []).append({"role": role, "content": content})
        self._store[chat_id] = self._store[chat_id][-100:]

    def recall(self, *, chat_id: str) -> list[dict]:
        return self._store.get(chat_id, [])


_fallback = InMemoryStoreFallback()
_redis_memory: RedisMemoryStore | None = None
try:
    _redis_memory = RedisMemoryStore()
except RedisError:
    _redis_memory = None


def remember_chat(*, chat_id: str, role: str, content: str) -> None:
    if _redis_memory is None:
        _fallback.remember(chat_id=chat_id, role=role, content=content)
        return
    try:
        _redis_memory.remember(chat_id=chat_id, role=role, content=content)
    except RedisError:
        _fallback.remember(chat_id=chat_id, role=role, content=content)


def recall_chat(*, chat_id: str) -> list[dict]:
    if _redis_memory is None:
        return _fallback.recall(chat_id=chat_id)
    try:
        return _redis_memory.recall(chat_id=chat_id)
    except RedisError:
        return _fallback.recall(chat_id=chat_id)
