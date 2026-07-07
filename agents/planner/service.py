from collections.abc import Callable

from agents.provider.base import BaseProvider


class PlannerService:
    def __init__(self, *, provider: BaseProvider, resolve_model: Callable[[], str]) -> None:
        self._provider = provider
        self._resolve_model = resolve_model

    async def plan(self, *, project_id: str, user_goal: str, context: dict) -> dict:
        prompt = (
            "You are AIRuntime planner. Return a short JSON object with keys "
            "`goal` (string) and `steps` (array of 3-5 strings) for this product request.\n"
            f"Project: {project_id}\nGoal: {user_goal}\nContext keys: {list(context.keys())}"
        )
        try:
            if hasattr(self._provider, "complete"):
                raw = await self._provider.complete(  # type: ignore[attr-defined]
                    messages=[{"role": "user", "content": prompt}],
                    model=self._resolve_model(),
                )
                import json
                import re

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    return {
                        "project_id": project_id,
                        "goal": parsed.get("goal", user_goal),
                        "steps": parsed.get("steps", ["analyze", "code", "test", "deploy"]),
                        "context_keys": list(context.keys()),
                    }
        except Exception:
            pass
        return {
            "project_id": project_id,
            "goal": user_goal,
            "steps": ["analyze requirements", "generate code", "run tests", "deploy runtime"],
            "context_keys": list(context.keys()),
        }
