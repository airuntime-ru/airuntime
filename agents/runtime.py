import json
import re
from collections.abc import AsyncIterator, Callable

from agents.coder.service import CoderService
from agents.conversation.service import ConversationService
from agents.deployer.service import DeployerService
from agents.planner.service import PlannerService
from agents.provider.base import BaseProvider
from agents.tester.service import TesterService
from agents.tools.executor import ToolExecutorService

RecallFn = Callable[[str], list[dict]]
RememberFn = Callable[[str, str, str], None]
ResolveModelFn = Callable[[], str]
DeployFn = Callable[..., dict]


class AIRuntimeEngine:
    def __init__(
        self,
        *,
        provider: BaseProvider,
        recall: RecallFn,
        remember: RememberFn,
        resolve_model: ResolveModelFn,
        deploy_fn: DeployFn,
    ) -> None:
        self.conversation = ConversationService(
            provider=provider,
            recall=recall,
            remember=remember,
            resolve_model=resolve_model,
        )
        self.planner = PlannerService(provider=provider, resolve_model=resolve_model)
        self.coder = CoderService(provider=provider, resolve_model=resolve_model)
        self.tester = TesterService()
        self.deployer = DeployerService(deploy_fn=deploy_fn)
        self.tools = ToolExecutorService()

    async def stream_reply(self, *, chat_id: str, user_message: str) -> AsyncIterator[str]:
        lowered = user_message.lower()
        if any(token in lowered for token in ("deploy", "launch", "ship", "release")):
            plan = await self.planner.plan(project_id=chat_id, user_goal=user_message, context={})
            summary = (
                f"Runtime plan: {', '.join(plan.get('steps', []))}. "
                f"Goal: {plan.get('goal', user_message)}"
            )
            user_message = f"{user_message}\n\n{summary}"

        async for chunk in self.conversation.stream_reply(chat_id=chat_id, user_message=user_message):
            yield chunk

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
