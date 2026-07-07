from collections.abc import AsyncIterator
from typing import Protocol


class Planner(Protocol):
    async def plan(self, *, project_id: str, user_goal: str, context: dict) -> dict: ...


class Coder(Protocol):
    async def execute(self, *, plan: dict, workspace_path: str) -> dict: ...


class Tester(Protocol):
    async def run(self, *, workspace_path: str, test_plan: dict) -> dict: ...


class Deployer(Protocol):
    async def deploy(self, *, project_id: str, artifact_ref: str, config: dict) -> dict: ...


class ConversationEngine(Protocol):
    async def stream_reply(self, *, chat_id: str, user_message: str) -> AsyncIterator[str]: ...


class ProviderClient(Protocol):
    async def stream(
        self, *, messages: list[dict], model: str, tools: list[dict]
    ) -> AsyncIterator[str]: ...


class MemoryStore(Protocol):
    async def recall(self, *, project_id: str, query: str) -> list[dict]: ...
    async def remember(self, *, project_id: str, item: dict) -> None: ...


class ToolExecutor(Protocol):
    async def call(self, *, name: str, args: dict, actor_id: str) -> dict: ...
