from collections.abc import Callable

from agents.provider.base import BaseProvider


class CoderService:
    def __init__(self, *, provider: BaseProvider, resolve_model: Callable[[], str]) -> None:
        self._provider = provider
        self._resolve_model = resolve_model

    async def execute(self, *, plan: dict, workspace_path: str) -> dict:
        prompt = (
            "You are AIRuntime coder. Summarize implementation actions in under 120 words.\n"
            f"Plan: {plan}\nWorkspace: {workspace_path}"
        )
        summary = ""
        try:
            if hasattr(self._provider, "complete"):
                summary = await self._provider.complete(  # type: ignore[attr-defined]
                    messages=[{"role": "user", "content": prompt}],
                    model=self._resolve_model(),
                )
        except Exception as exc:
            summary = f"Coder fallback: {exc}"
        return {
            "status": "ok",
            "workspace_path": workspace_path,
            "plan_steps": plan.get("steps", []),
            "summary": summary.strip() or "Implementation scaffold prepared.",
        }
