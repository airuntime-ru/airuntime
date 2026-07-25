"""BudgetEngine (spec section 18): credits/tokens/wall-time/attempt/build/deploy/mcp/skill/
context/output budgets, checked by engine.py before each operation.

Wired to REAL credits via billing.record_usage (charge_credits_for_run below), not the flat
char-count heuristic chat.py's non-orchestrated path still uses on its own turns
(chat.py:1273's `usage_cost = max(100, len(...))`) - an orchestrated run's cost is the sum of
real per-task provider usage when reported, falling back to that same heuristic only when a
task's AgentDone genuinely carried no usage payload (better than silently charging nothing).

`BudgetTracker` itself is pure in-memory, per-run state (mirrors LoopDetector's own shape) -
engine.py owns one instance per run and calls `charge_credits_for_run` at natural checkpoints
against the real DB/ledger, rather than this module opening its own DB session.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from src.db.models.user import User
from src.services import billing
from src.services.orchestration.context_engine import clip_text

_CREDITS_PER_1000_TOKENS = 10
_APPROACHING_RATIO = 0.8


def estimate_task_cost(*, usage: dict | None, summary_text: str) -> int:
    if usage:
        total = usage.get("total_tokens")
        if not isinstance(total, int):
            parts = [
                usage.get(key)
                for key in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens")
            ]
            summed = sum(p for p in parts if isinstance(p, int))
            total = summed or None
        if isinstance(total, int) and total > 0:
            return max(100, (total * _CREDITS_PER_1000_TOKENS) // 1000)
    # Fallback: the same heuristic chat.py's non-orchestrated path already uses (visible-reply
    # char count) - better than charging nothing when a provider/executor reported no usage.
    return max(100, len(summary_text or ""))


def charge_credits_for_run(
    db: Session,
    user: User,
    *,
    project_id: uuid.UUID | str,
    amount: int,
    project_name: str | None = None,
) -> None:
    """Thin pass-through to billing.record_usage - kept here (not called directly by engine.py)
    so every orchestration credit charge goes through one named entry point that's easy to grep
    for and easy to unit test independent of the engine's own control flow."""
    if amount <= 0:
        return
    billing.record_usage(db, user, project_id=project_id, amount=amount, project_name=project_name)


class BudgetStatus(StrEnum):
    OK = "ok"
    APPROACHING = "approaching"
    EXCEEDED = "exceeded"


@dataclass
class BudgetLimits:
    max_credits: int | None = None
    max_wall_seconds: int | None = None
    max_tasks: int | None = None
    max_task_attempts: int = 3
    max_build_attempts: int = 5
    max_deploy_attempts: int = 3
    max_mcp_calls: int | None = None
    max_skill_calls: int | None = None
    max_context_chars: int = 32_000
    max_output_chars: int = 20_000


@dataclass
class BudgetUsage:
    credits_used: int = 0
    tasks_run: int = 0
    build_attempts: int = 0
    deploy_attempts: int = 0
    mcp_calls: int = 0
    skill_calls: int = 0
    _started_at: float = field(default_factory=time.monotonic)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_at


@dataclass
class BudgetCheckResult:
    status: BudgetStatus
    dimension: str | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status != BudgetStatus.EXCEEDED


class BudgetTracker:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.usage = BudgetUsage()

    def _dimensions(self) -> list[tuple[str, float, float | None]]:
        return [
            ("credits", self.usage.credits_used, self.limits.max_credits),
            ("wall_seconds", self.usage.elapsed_seconds(), self.limits.max_wall_seconds),
            ("tasks", self.usage.tasks_run, self.limits.max_tasks),
            ("build_attempts", self.usage.build_attempts, self.limits.max_build_attempts),
            ("deploy_attempts", self.usage.deploy_attempts, self.limits.max_deploy_attempts),
            ("mcp_calls", self.usage.mcp_calls, self.limits.max_mcp_calls),
            ("skill_calls", self.usage.skill_calls, self.limits.max_skill_calls),
        ]

    def check(self) -> BudgetCheckResult:
        """Call before starting a new task/build/deploy/mcp/skill operation. EXCEEDED means the
        caller must stop that class of operation entirely; APPROACHING means the caller should
        degrade gracefully (prefer a deterministic skill over a specialist agent, compress
        context harder, skip an optional review step, tell the user about the risk) but may
        still proceed - see engine.py for where each of those degradations is applied."""
        dimensions = self._dimensions()
        for name, used, limit in dimensions:
            if limit is not None and used >= limit:
                return BudgetCheckResult(
                    status=BudgetStatus.EXCEEDED, dimension=name, message=f"{name}: {used}/{limit}"
                )
        for name, used, limit in dimensions:
            if limit is not None and limit > 0 and used >= limit * _APPROACHING_RATIO:
                return BudgetCheckResult(
                    status=BudgetStatus.APPROACHING,
                    dimension=name,
                    message=f"{name}: {used}/{limit} (approaching)",
                )
        return BudgetCheckResult(status=BudgetStatus.OK)

    def record_task(self) -> None:
        self.usage.tasks_run += 1

    def record_build_attempt(self) -> None:
        self.usage.build_attempts += 1

    def record_deploy_attempt(self) -> None:
        self.usage.deploy_attempts += 1

    def record_mcp_call(self) -> None:
        self.usage.mcp_calls += 1

    def record_skill_call(self) -> None:
        self.usage.skill_calls += 1

    def record_credits(self, amount: int) -> None:
        self.usage.credits_used += max(0, amount)

    def clip_context(self, text: str) -> str:
        return clip_text(text, max_chars=self.limits.max_context_chars)

    def clip_output(self, text: str) -> str:
        return clip_text(text, max_chars=self.limits.max_output_chars)

    def attempts_allowed(self, attempt: int, *, override_max: int | None = None) -> bool:
        ceiling = override_max if override_max is not None else self.limits.max_task_attempts
        return attempt < ceiling
