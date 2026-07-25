"""Tests for services/orchestration/planner.py. No live LLM: `complete_structured` is
monkeypatched where planner.py imported it, matching this repo's existing test convention
(see test_product_pipeline.py's `_make_complete_structured`)."""

from __future__ import annotations

import pytest

from src.services.orchestration import planner
from src.services.orchestration.schemas import (
    AcceptanceCriterion,
    ExecutionPlan,
    PlannedTask,
    SpecialistRole,
)


def _task(
    local_id: str, deps: list[str] | None = None, role: SpecialistRole = SpecialistRole.IMPLEMENTER
) -> PlannedTask:
    return PlannedTask(
        local_id=local_id,
        title=f"Task {local_id}",
        role=role,
        goal=f"do {local_id}",
        reason="planned",
        dependencies=deps or [],
        acceptance_criteria=[
            AcceptanceCriterion(
                id=f"{local_id}-ac1", description="works", verification_method="build"
            )
        ],
    )


class TestFindDependencyCycle:
    def test_no_cycle_in_dag(self) -> None:
        tasks = [_task("a"), _task("b", ["a"]), _task("c", ["a", "b"])]
        assert planner.find_dependency_cycle(tasks) is None

    def test_direct_cycle(self) -> None:
        tasks = [_task("a", ["b"]), _task("b", ["a"])]
        cycle = planner.find_dependency_cycle(tasks)
        assert cycle is not None
        assert set(cycle) == {"a", "b"}

    def test_self_dependency_rejected_at_model_level(self) -> None:
        with pytest.raises(ValueError, match="cannot depend on itself"):
            _task("a", ["a"])

    def test_indirect_cycle(self) -> None:
        tasks = [_task("a", ["c"]), _task("b", ["a"]), _task("c", ["b"])]
        cycle = planner.find_dependency_cycle(tasks)
        assert cycle is not None
        assert {"a", "b", "c"} <= set(cycle)

    def test_dangling_dependency_is_not_a_cycle(self) -> None:
        tasks = [_task("a", ["ghost"])]
        assert planner.find_dependency_cycle(tasks) is None


class TestValidatePlanStructure:
    def _plan(self, tasks: list[PlannedTask], complexity: str = "compound") -> ExecutionPlan:
        return ExecutionPlan(goal="g", complexity=complexity, tasks=tasks)

    def test_valid_plan_has_no_errors(self) -> None:
        plan = self._plan([_task("a"), _task("b", ["a"])])
        assert planner.validate_plan_structure(plan, max_tasks=10) == []

    def test_too_many_tasks(self) -> None:
        plan = self._plan([_task(str(i)) for i in range(5)])
        errors = planner.validate_plan_structure(plan, max_tasks=3)
        assert any("exceeding the limit" in e for e in errors)

    def test_dangling_dependency_reported(self) -> None:
        plan = self._plan([_task("a", ["missing"])])
        errors = planner.validate_plan_structure(plan, max_tasks=10)
        assert any("unknown local_id" in e for e in errors)

    def test_cycle_reported(self) -> None:
        plan = self._plan([_task("a", ["b"]), _task("b", ["a"])])
        errors = planner.validate_plan_structure(plan, max_tasks=10)
        assert any("cycle" in e for e in errors)

    def test_simple_complexity_with_multiple_tasks_rejected(self) -> None:
        plan = self._plan([_task("a"), _task("b")], complexity="simple")
        errors = planner.validate_plan_structure(plan, max_tasks=10)
        assert any("complexity=simple" in e for e in errors)


class TestBuildSingleTaskPlan:
    def test_produces_one_implementer_task(self) -> None:
        plan = planner.build_single_task_plan("add a contact form", reason="test")
        assert plan.complexity == "simple"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].role == SpecialistRole.IMPLEMENTER
        assert planner.validate_plan_structure(plan, max_tasks=10) == []


@pytest.mark.asyncio
class TestGeneratePlan:
    async def test_short_message_skips_llm_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _boom(**kwargs):  # noqa: ANN003
            raise AssertionError("complete_structured must not be called for trivial requests")

        monkeypatch.setattr(planner, "complete_structured", _boom)
        result = await planner.generate_plan(
            user_message="fix typo",
            project_context_summary="",
            provider_name="openai",
            model="m",
            api_key="k",
        )
        assert result.source == "heuristic_simple"
        assert len(result.plan.tasks) == 1

    async def test_valid_llm_plan_is_used_as_is(self, monkeypatch: pytest.MonkeyPatch) -> None:
        good_plan = ExecutionPlan(
            goal="build a shop",
            complexity="compound",
            tasks=[_task("backend"), _task("frontend", ["backend"])],
        )

        async def _fake_complete(**kwargs):  # noqa: ANN003
            assert kwargs["response_model"] is ExecutionPlan
            return good_plan

        monkeypatch.setattr(planner, "complete_structured", _fake_complete)
        result = await planner.generate_plan(
            user_message="x" * 200,
            project_context_summary="ctx",
            provider_name="openai",
            model="m",
            api_key="k",
        )
        assert result.source == "llm"
        assert result.plan is good_plan
        assert result.errors == []

    async def test_llm_failure_falls_back_to_single_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_none(**kwargs):  # noqa: ANN003
            return None

        monkeypatch.setattr(planner, "complete_structured", _fake_none)
        result = await planner.generate_plan(
            user_message="y" * 200,
            project_context_summary="",
            provider_name="openai",
            model="m",
            api_key="k",
        )
        assert result.source == "fallback_llm_failed"
        assert len(result.plan.tasks) == 1

    async def test_invalid_plan_gets_one_repair_attempt_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cyclic_plan = ExecutionPlan(
            goal="g", complexity="compound", tasks=[_task("a", ["b"]), _task("b", ["a"])]
        )
        fixed_plan = ExecutionPlan(
            goal="g", complexity="compound", tasks=[_task("a"), _task("b", ["a"])]
        )
        calls = []

        async def _fake_sequence(**kwargs):  # noqa: ANN003
            calls.append(kwargs["user_text"])
            return cyclic_plan if len(calls) == 1 else fixed_plan

        monkeypatch.setattr(planner, "complete_structured", _fake_sequence)
        result = await planner.generate_plan(
            user_message="z" * 200,
            project_context_summary="",
            provider_name="openai",
            model="m",
            api_key="k",
        )
        assert len(calls) == 2
        assert "не прошёл структурную проверку" in calls[1]
        assert result.source == "llm_repaired"
        assert result.plan is fixed_plan

    async def test_invalid_plan_after_repair_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cyclic_plan = ExecutionPlan(
            goal="g", complexity="compound", tasks=[_task("a", ["b"]), _task("b", ["a"])]
        )

        async def _always_cyclic(**kwargs):  # noqa: ANN003
            return cyclic_plan

        monkeypatch.setattr(planner, "complete_structured", _always_cyclic)
        result = await planner.generate_plan(
            user_message="w" * 200,
            project_context_summary="",
            provider_name="openai",
            model="m",
            api_key="k",
        )
        assert result.source == "fallback_invalid"
        assert len(result.plan.tasks) == 1
        assert any("cycle" in e for e in result.errors)


class TestDeriveComplexity:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(0, "simple"), (1, "simple"), (2, "compound"), (4, "compound"), (5, "large")],
    )
    def test_thresholds(self, count: int, expected: str) -> None:
        assert planner.derive_complexity_from_task_count(count) == expected
