class MemoryService:
    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    async def recall(self, *, project_id: str, query: str) -> list[dict]:
        _ = query
        return self._store.get(project_id, [])

    async def remember(self, *, project_id: str, item: dict) -> None:
        self._store.setdefault(project_id, []).append(item)
