"""Builds a versioned ExecutionPlan (a bounded DAG, not the old orchestrator.py's flat
{"subtasks":[...]} list) and structurally validates it before anything downstream ever sees it.

Reuses `pipeline_llm.complete_structured` verbatim for the actual model call - it already does
exactly what a planner call needs (JSON-schema-constrained one-shot completion, one repair
round-trip on a bad response, `None` on total failure) for the product pipeline's brief/UX/
visual/review calls, and `ExecutionPlan` is just another Pydantic response_model to it.

Never returns "no plan" - a call that fails outright, or whose result never becomes
structurally valid even after one LLM repair round-trip, degrades to a single-task plan
(role=Implementer, goal=the raw request) rather than blocking the run. Every request, however
small, ends up going through the same plan -> contract -> validation pipeline (spec section 4:
"Для маленького запроса система может создать одну задачу, но она всё равно должна проходить
через единый execution contract и validation").

The planner never assigns tools/skills/paths directly to a task beyond *suggestions*
(PlannedTask.suggested_skills, .relevant_paths, .required_capabilities) - role_policy.py and
contract_builder.py are what actually compute a task's rights, always as a subset of what the
plan asked for, never a superset.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from src.core.config import settings
from src.services.agent.pipeline_llm import complete_structured
from src.services.orchestration.role_policy import ROLE_REGISTRY
from src.services.orchestration.schemas import (
    AcceptanceCriterion,
    Complexity,
    ExecutionBudget,
    ExecutionPlan,
    PlannedTask,
    SpecialistRole,
)

logger = logging.getLogger(__name__)

PlanSource = Literal[
    "heuristic_simple", "llm", "llm_repaired", "fallback_llm_failed", "fallback_invalid"
]

# Below this length, skip the planning call entirely - same philosophy as the old
# orchestrator.py's _MIN_MESSAGE_CHARS_FOR_PLANNING gate (120), a little more generous since a
# short request still gets a *real* single-task plan now, not just "don't decompose".
_TRIVIAL_MESSAGE_CHARS = 160

_PLANNING_SYSTEM_PROMPT_TEMPLATE = """Ты - планировщик платформы AIRuntime. По запросу
пользователя и текущему состоянию проекта построй ExecutionPlan - ограниченный граф задач, а
НЕ линейный список.

Доступные роли (SpecialistRole) и их назначение:
{role_catalog}

Правила:
- Каждая задача (PlannedTask) должна иметь уникальный local_id (короткая ASCII-строка вроде
  "backend_api", "landing_page").
- dependencies - список local_id других задач ЭТОГО плана, от которых зависит задача. Не
  создавай циклов.
- Задачи без общих file-путей и с execution_preference, допускающим параллельность, можно
  оставить независимыми (пустой dependencies) - это разрешит платформе выполнить их параллельно
  (read-only задачи всегда параллельны; write-задачи - только через изолированный worktree,
  который платформа создаст сама, если докажет независимость путей).
- НЕ назначай инструменты (tools) напрямую - это делает платформа на основе роли.
- Не создавай более {max_tasks} задач.
- Если запрос по сути один маленький кусок работы - создай ОДНУ задачу, это нормально.
- Поля title/goal/reason/description объектов пиши по-русски (это текст для пользователя и для
  исполнителя), но имена JSON-полей и enum-значения (role, execution_preference, write_scope,
  risk_level, verification_method) оставляй ровно как в схеме - только на английском.
- complexity: "simple" для одной задачи, "compound" для нескольких связанных задач одного
  проекта, "large" для многомодульной работы (например сайт + отдельный Telegram-бот).
- Каждая задача должна нести хотя бы один acceptance_criterion, проверяемый одним из методов:
  build, test, preview, runtime, manual, llm_review.
"""


def _role_catalog_text() -> str:
    lines = []
    for role in SpecialistRole:
        policy = ROLE_REGISTRY[role]
        lines.append(
            f"- {role.value}: {policy.title} - {policy.system_prompt.splitlines()[0][:140]}"
        )
    return "\n".join(lines)


def build_planning_system_prompt(*, max_tasks: int) -> str:
    return _PLANNING_SYSTEM_PROMPT_TEMPLATE.format(
        role_catalog=_role_catalog_text(), max_tasks=max_tasks
    )


def derive_complexity_from_task_count(task_count: int) -> Complexity:
    if task_count <= 1:
        return "simple"
    if task_count <= 4:
        return "compound"
    return "large"


def build_single_task_plan(user_message: str, *, reason: str) -> ExecutionPlan:
    goal = user_message.strip()[:2000] or "Выполнить запрос пользователя"
    return ExecutionPlan(
        goal=goal,
        complexity="simple",
        tasks=[
            PlannedTask(
                local_id="main",
                title=goal[:120],
                role=SpecialistRole.IMPLEMENTER,
                goal=goal,
                reason=reason,
                execution_preference="either",
                dependencies=[],
                relevant_paths=[],
                write_scope="full_workspace",
                # Without at least one criterion, contract_builder.score_task_contract() can
                # never pass this task's contract (it hard-requires acceptance_criteria to be
                # non-empty) - every heuristic/fallback plan would dead-end into a replan loop
                # before ever reaching an executor. "build" is the one verification method every
                # website/bot task can be checked against regardless of what the request asked.
                acceptance_criteria=[
                    AcceptanceCriterion(
                        id="main_goal_met",
                        description=f"Запрос пользователя выполнен: {goal[:200]}",
                        verification_method="build",
                    )
                ],
            )
        ],
        final_acceptance_criteria=[],
        risks=[],
        estimated_budget=ExecutionBudget(
            max_attempts_per_task=settings.orchestration_max_task_attempts
        ),
    )


def find_dependency_cycle(tasks: list[PlannedTask]) -> list[str] | None:
    """DFS-based cycle detection. Returns the cyclic path (local_ids) if one exists, else None.
    Dangling dependency references (pointing at a local_id that doesn't exist) are ignored here
    and reported separately by `validate_plan_structure`."""
    graph = {t.local_id: t.dependencies for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            if color[dep] == GRAY:
                cycle_start = path.index(dep)
                return [*path[cycle_start:], dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        path.pop()
        color[node] = BLACK
        return None

    for local_id in graph:
        if color[local_id] == WHITE:
            found = visit(local_id)
            if found:
                return found
    return None


def validate_plan_structure(plan: ExecutionPlan, *, max_tasks: int) -> list[str]:
    """Structural validation only (graph shape) - role/tool/path *rights* are re-derived by
    role_policy.py regardless of what the plan says, so this does not need to (and must not)
    try to enforce policy itself."""
    errors: list[str] = []

    if len(plan.tasks) > max_tasks:
        errors.append(f"plan has {len(plan.tasks)} tasks, exceeding the limit of {max_tasks}")

    seen_ids: set[str] = set()
    for task in plan.tasks:
        if task.local_id in seen_ids:
            errors.append(f"duplicate local_id: {task.local_id!r}")
        seen_ids.add(task.local_id)

    for task in plan.tasks:
        for dep in task.dependencies:
            if dep not in seen_ids:
                errors.append(f"task {task.local_id!r} depends on unknown local_id {dep!r}")

    cycle = find_dependency_cycle(plan.tasks)
    if cycle:
        errors.append(f"dependency cycle detected: {' -> '.join(cycle)}")

    if plan.complexity == "simple" and len(plan.tasks) > 1:
        errors.append("complexity=simple but plan declares more than one task")

    if not plan.tasks:
        errors.append("plan has no tasks")

    return errors


@dataclass
class PlanGenerationResult:
    plan: ExecutionPlan
    source: PlanSource
    errors: list[str] = field(default_factory=list)


async def generate_plan(
    *,
    user_message: str,
    project_context_summary: str,
    provider_name: str,
    model: str,
    api_key: str,
    max_tasks: int | None = None,
    timeout_seconds: int = 90,
) -> PlanGenerationResult:
    max_tasks = max_tasks or settings.orchestration_max_plan_tasks

    if len(user_message.strip()) < _TRIVIAL_MESSAGE_CHARS:
        return PlanGenerationResult(
            plan=build_single_task_plan(user_message, reason="short request - planning skipped"),
            source="heuristic_simple",
        )

    system_prompt = build_planning_system_prompt(max_tasks=max_tasks)
    user_text = (
        f"Состояние проекта:\n{project_context_summary}\n\nЗапрос пользователя:\n{user_message}"
    )

    raw_plan = await complete_structured(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        user_text=user_text,
        response_model=ExecutionPlan,
        timeout_seconds=timeout_seconds,
    )
    if raw_plan is None:
        logger.info("planner: LLM call produced no usable plan, falling back to single-task plan")
        return PlanGenerationResult(
            plan=build_single_task_plan(user_message, reason="planner call failed"),
            source="fallback_llm_failed",
            errors=["planner_call_failed"],
        )

    errors = validate_plan_structure(raw_plan, max_tasks=max_tasks)
    if not errors:
        return PlanGenerationResult(plan=raw_plan, source="llm")

    logger.info(
        "planner: LLM plan failed structural validation (%s), asking for one repair", errors
    )
    repair_text = (
        f"{user_text}\n\n--- Твой предыдущий план не прошёл структурную проверку ---\n"
        f"Ошибки: {'; '.join(errors)}\nИсправь именно граф зависимостей/local_id и верни план заново."
    )
    repaired_plan = await complete_structured(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        user_text=repair_text,
        response_model=ExecutionPlan,
        timeout_seconds=timeout_seconds,
    )
    if repaired_plan is not None:
        repaired_errors = validate_plan_structure(repaired_plan, max_tasks=max_tasks)
        if not repaired_errors:
            return PlanGenerationResult(plan=repaired_plan, source="llm_repaired")
        errors = repaired_errors

    logger.warning(
        "planner: plan invalid even after repair (%s), falling back to single-task plan", errors
    )
    return PlanGenerationResult(
        plan=build_single_task_plan(user_message, reason="plan validation failed twice"),
        source="fallback_invalid",
        errors=errors,
    )
