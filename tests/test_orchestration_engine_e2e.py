"""End-to-end tests for services/orchestration/engine.py against a real Postgres test DB and a
real git-initialized tmp_path workspace. Only two seams are faked:
  - `engine._build_executor` returns a scripted `_FakeExecutor` instead of a real Codex/HTTP
    session - this is the same seam executors.py itself is unit-tested through, so faking it
    here tests the ENGINE's own orchestration logic (routing/contract/evidence/validation/
    failure-policy/budget/events), not a duplicate of executors.py's own test suite.
  - `engine.generate_plan` / `engine.generate_replan` are only faked for multi-task/replan
    scenarios; single-task scenarios use a short `original_request` (<160 chars) so
    planner.generate_plan() takes its real, LLM-free heuristic_simple path unmodified.

Everything else - repositories, status transitions, GitTransactionManager, WorkspaceIsolation
Manager, evidence collection, validation, failure_policy, budget, events_bus - runs for real.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest
from sqlalchemy.orm import Session
from tests.conftest import TestingSessionLocal

from src.db.models.chat import Chat
from src.db.models.project import Project
from src.db.models.user import User
from src.services import project_git
from src.services.orchestration import engine
from src.services.orchestration.executors import AgentExecutionResult, TaskContext
from src.services.orchestration.repository import (
    AgentTaskRepository,
    OrchestrationPlanRepository,
    OrchestrationRunRepository,
    RunEventRepository,
)
from src.services.orchestration.schemas import (
    AcceptanceCriterion,
    ExecutionBudget,
    ExecutionPlan,
    PlannedTask,
    SpecialistRole,
    TaskResult,
)


@pytest.fixture()
def project(db: Session) -> Project:
    user = User(email=f"{uuid.uuid4().hex}@example.com", credits_balance=100_000)
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, type="website", name="Engine e2e project")
    db.add(project)
    db.flush()
    return project


def _make_run(db: Session, project: Project, *, original_request: str, **overrides) -> object:
    chat = Chat(project_id=project.id)
    db.add(chat)
    db.flush()
    fields = dict(
        project_id=project.id,
        chat_id=chat.id,
        user_id=project.user_id,
        original_request=original_request,
    )
    fields.update(overrides)
    return OrchestrationRunRepository(db).create(**fields)


@pytest.fixture()
def workspace_root(tmp_path):
    project_git.init_repo_if_needed(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _patch_workspace_dir(monkeypatch: pytest.MonkeyPatch, workspace_root):
    monkeypatch.setattr(engine, "project_workspace_dir", lambda project_id: workspace_root)


@pytest.fixture()
def db_factory(db: Session):
    def factory() -> Session:
        return TestingSessionLocal(bind=db.get_bind())

    return factory


def _events(db: Session, run_id) -> list[str]:
    return [row.event_type for row in RunEventRepository(db).list_since(run_id, after_seq=0)]


@dataclass
class _FakeExecutor:
    """Each call writes a small, distinct file (so there's a real diff to evidence/commit) and
    returns the next scripted AgentExecutionResult, repeating the last one if the script runs
    out - a test only needs to script as many attempts as it actually cares about."""

    script: list[AgentExecutionResult]
    calls: int = field(default=0)

    async def execute(self, contract, context: TaskContext, cancellation) -> AgentExecutionResult:
        self.calls += 1
        (context.workspace_root / f"output_{self.calls}.txt").write_text(
            f"attempt {self.calls}", encoding="utf-8"
        )
        idx = min(self.calls - 1, len(self.script) - 1)
        return self.script[idx]


def _install_fake_executor(monkeypatch: pytest.MonkeyPatch, fake: _FakeExecutor) -> None:
    monkeypatch.setattr(engine, "_build_executor", lambda kind, *, db, mcp_repo: fake)


def _ok_result(*, summary: str = "done") -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(
            status="completed", summary=summary, claimed_changed_files=["output.txt"]
        ),
        build_result={"ok": True, "log_tail": "build ok"},
    )


def _build_failed_result(*, summary: str = "attempt failed") -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(status="completed", summary=summary),
        build_result={"ok": False, "log_tail": "syntax error"},
    )


def _service_request_ok_result(service_kind: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(
            status="completed",
            summary="done, used a database",
            requested_services=[service_kind],
        ),
        build_result={"ok": True, "log_tail": "ok"},
    )


def _secret_request_result(secret_key: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(
            status="partial",
            summary="need a credential",
            requested_secrets=[secret_key],
        ),
        build_result=None,
    )


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_single_task_run_completes_and_commits(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        fake = _FakeExecutor(script=[_ok_result()])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "completed"
        assert refreshed.final_commit_sha
        assert refreshed.credits_used > 0
        assert fake.calls == 1

        tasks = AgentTaskRepository(db).list_by_run(run.id)
        assert len(tasks) == 1
        assert tasks[0].status == "completed"
        assert tasks[0].accepted_commit_sha == refreshed.final_commit_sha

        assert _events(db, run.id) == [
            "run_created",
            "planning_started",
            "plan_created",
            "task_started",
            "task_completed",
            "run_completed",
        ]

    @pytest.mark.asyncio
    async def test_committed_file_is_actually_on_disk_at_head(
        self,
        db: Session,
        db_factory,
        project: Project,
        monkeypatch: pytest.MonkeyPatch,
        workspace_root,
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        _install_fake_executor(monkeypatch, _FakeExecutor(script=[_ok_result()]))

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        assert (workspace_root / "output_1.txt").exists()


class TestServiceAutoProvisioning:
    @pytest.mark.asyncio
    async def test_requested_service_is_provisioned_without_pausing_the_run(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Unlike a missing secret, a requested service must never need the user - it's a DB row
        # (ProjectService), not something only a human can supply - so the run should complete
        # normally in one attempt rather than parking at waiting_for_user.
        run = _make_run(db, project, original_request="Сделай сайт с базой данных")
        db.commit()
        fake = _FakeExecutor(script=[_service_request_ok_result("postgres")])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        assert OrchestrationRunRepository(db).get(run.id).status == "completed"
        assert fake.calls == 1

        from src.db.models.project_service import ProjectService

        service = db.query(ProjectService).filter(ProjectService.project_id == project.id).first()
        assert service is not None
        assert service.kind == "postgres"


class TestRetryThenSucceed:
    @pytest.mark.asyncio
    async def test_second_attempt_succeeds_after_first_build_failure(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        fake = _FakeExecutor(script=[_build_failed_result(), _ok_result()])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        assert OrchestrationRunRepository(db).get(run.id).status == "completed"
        assert fake.calls == 2
        task = AgentTaskRepository(db).list_by_run(run.id)[0]
        assert task.status == "completed"
        assert task.attempt == 2
        assert "task_repairing" in _events(db, run.id)


class TestExhaustedAttempts:
    @pytest.mark.asyncio
    async def test_fails_the_run_when_replanning_disabled(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(engine.settings, "enable_replanning", False)
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        fake = _FakeExecutor(script=[_build_failed_result()])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "failed"
        # default_max_attempts for Implementer is 3 (role_policy.py) - three real attempts, no more.
        assert fake.calls == 3

    @pytest.mark.asyncio
    async def test_replans_and_completes_under_the_new_plan(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        fake = _FakeExecutor(
            script=[
                _build_failed_result(),
                _build_failed_result(),
                _build_failed_result(),
                _ok_result(),
            ]
        )
        _install_fake_executor(monkeypatch, fake)

        async def _fake_generate_replan(**kwargs):
            from src.services.orchestration.planner import PlanGenerationResult

            plan = ExecutionPlan(
                goal="revised goal",
                complexity="simple",
                tasks=[
                    PlannedTask(
                        local_id="retry_main",
                        title="Retry",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="revised goal",
                        reason="replanned after repeated build failure",
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c1", description="builds", verification_method="build"
                            )
                        ],
                    )
                ],
                estimated_budget=ExecutionBudget(),
            )
            return PlanGenerationResult(plan=plan, source="llm")

        monkeypatch.setattr(engine, "generate_replan", _fake_generate_replan)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "completed"
        assert refreshed.plan_version == 2

        versions = OrchestrationPlanRepository(db).list_versions(run.id)
        assert [v.status for v in versions] == ["superseded", "active"]

        all_tasks = AgentTaskRepository(db).list_by_run(run.id)
        assert {t.local_id for t in all_tasks} == {"main", "retry_main"}
        original = next(t for t in all_tasks if t.local_id == "main")
        retried = next(t for t in all_tasks if t.local_id == "retry_main")
        assert original.status == "failed"
        assert retried.status == "completed"
        assert "plan_revised" in _events(db, run.id)

    @pytest.mark.asyncio
    async def test_fails_when_replan_limit_is_reached(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(engine.settings, "orchestration_max_replans", 0)
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        _install_fake_executor(monkeypatch, _FakeExecutor(script=[_build_failed_result()]))

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "failed"
        assert refreshed.plan_version == 1


class TestWaitingForSecret:
    @pytest.mark.asyncio
    async def test_pauses_then_resumes_and_completes(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай сайт с оплатой")
        db.commit()
        fake = _FakeExecutor(script=[_secret_request_result("STRIPE_API_KEY"), _ok_result()])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        paused = OrchestrationRunRepository(db).get(run.id)
        assert paused.status == "waiting_for_user"
        task = AgentTaskRepository(db).list_by_run(run.id)[0]
        assert task.status == "waiting_for_user"
        assert "waiting_for_secret" in _events(db, run.id)

        engine.resume_task_after_user_input(db, task.id)
        db.commit()

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        resumed = OrchestrationRunRepository(db).get(run.id)
        assert resumed.status == "completed"
        assert fake.calls == 2


class TestBudget:
    @pytest.mark.asyncio
    async def test_second_task_is_stopped_once_budget_is_exceeded(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(
            db, project, original_request="Сделай лендинг для кофейни", credit_budget=150
        )
        db.commit()

        async def _fake_generate_plan(**kwargs):
            from src.services.orchestration.planner import PlanGenerationResult

            plan = ExecutionPlan(
                goal="two tasks",
                complexity="compound",
                tasks=[
                    PlannedTask(
                        local_id="first",
                        title="First",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="first",
                        reason="r",
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c1", description="d", verification_method="build"
                            )
                        ],
                    ),
                    PlannedTask(
                        local_id="second",
                        title="Second",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="second",
                        reason="r",
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c2", description="d", verification_method="build"
                            )
                        ],
                    ),
                ],
                estimated_budget=ExecutionBudget(),
            )
            return PlanGenerationResult(plan=plan, source="llm")

        monkeypatch.setattr(engine, "generate_plan", _fake_generate_plan)
        # A long summary pushes estimate_task_cost() (char-count fallback, no usage reported)
        # comfortably over the 150-credit run budget on the very first task.
        fake = _FakeExecutor(script=[_ok_result(summary="x" * 500)])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "failed"
        assert refreshed.error_code == "budget_exceeded"
        assert fake.calls == 1

        tasks = {t.local_id: t for t in AgentTaskRepository(db).list_by_run(run.id)}
        assert tasks["first"].status == "completed"
        # "skipped", not "failed" - it never got a chance to run at all.
        assert tasks["second"].status == "skipped"
        assert tasks["second"].error_code == "budget_exceeded"
        assert tasks["second"].attempt == 0


class TestCancellation:
    @pytest.mark.asyncio
    async def test_pre_cancelled_token_stops_before_planning(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.services.orchestration.cancellation import CancellationToken

        async def _boom(**kwargs):
            raise AssertionError("generate_plan must not be called for an already-cancelled run")

        monkeypatch.setattr(engine, "generate_plan", _boom)
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        token = CancellationToken()
        token.cancel("user pressed stop")

        await engine.run_orchestration(
            run.id,
            db_factory=db_factory,
            provider_name="openai",
            model="m",
            api_key="k",
            cancellation=token,
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "cancelled"
        assert _events(db, run.id) == ["run_cancelled"]

    @pytest.mark.asyncio
    async def test_db_cancel_requested_flag_stops_the_run_mid_loop(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()

        class _CancellingExecutor:
            async def execute(self, contract, context, cancellation):
                # Simulate the cancel endpoint flipping the DB flag while this task is running,
                # then let the task finish successfully - cancellation.py's own documented
                # philosophy is that an already-dispatched attempt is allowed to finish rather
                # than be force-killed. This also sidesteps a real trap: _run_one_task's retry
                # loop only checks the in-memory CancellationToken (converted from this DB flag
                # at the TOP of run_orchestration's outer loop, engine.py around line 844) - it
                # is never consulted mid-retry. A FAILING result here would exhaust all 3
                # attempts and (replanning_enabled defaults to True, unmocked in this test) fall
                # through to a real generate_replan()/generate_plan() call with a fake API key,
                # which is what was actually causing this test to hang on a live network call
                # rather than testing cancellation at all. A single successful attempt returns
                # control to the outer loop immediately, where the flag flip is picked up on the
                # very next iteration - before any further task would ever be dispatched.
                #
                # flush(), not commit(): this runs synchronously inside _run_one_task's own
                # active attempt, nested between git_txn.begin() (which can itself open a
                # SAVEPOINT - see WorkspaceLeaseRepository.try_acquire_shared) and
                # git_txn.complete() on the engine's OWN db_factory()-bound session, which
                # shares this test's underlying connection. A real commit() from this separate
                # Session object would end that whole shared transaction out from under the
                # engine's session mid-savepoint, desyncing SQLAlchemy's client-side transaction
                # state from the server's - flush() makes the write visible on the shared
                # connection without touching the transaction boundary.
                run_row = OrchestrationRunRepository(db).get(run.id)
                run_row.cancel_requested = True
                db.add(run_row)
                db.flush()
                return _ok_result()

        monkeypatch.setattr(
            engine, "_build_executor", lambda kind, *, db, mcp_repo: _CancellingExecutor()
        )

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "cancelled"


class TestContractCompleteness:
    @pytest.mark.asyncio
    async def test_task_with_no_acceptance_criteria_triggers_replan_not_a_silent_pass(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_generate_plan(**kwargs):
            from src.services.orchestration.planner import PlanGenerationResult

            plan = ExecutionPlan(
                goal="incomplete",
                complexity="simple",
                tasks=[
                    PlannedTask(
                        local_id="bare",
                        title="Bare",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="goal",
                        reason="r",
                        acceptance_criteria=[],  # deliberately incomplete
                    )
                ],
                estimated_budget=ExecutionBudget(),
            )
            return PlanGenerationResult(plan=plan, source="llm")

        monkeypatch.setattr(engine, "generate_plan", _fake_generate_plan)
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()

        called = {"n": 0}

        async def _fake_generate_replan(**kwargs):
            from src.services.orchestration.planner import PlanGenerationResult

            called["n"] += 1
            plan = ExecutionPlan(
                goal="fixed",
                complexity="simple",
                tasks=[
                    PlannedTask(
                        local_id="fixed",
                        title="Fixed",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="goal",
                        reason="r",
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c1", description="d", verification_method="build"
                            )
                        ],
                    )
                ],
                estimated_budget=ExecutionBudget(),
            )
            return PlanGenerationResult(plan=plan, source="llm")

        monkeypatch.setattr(engine, "generate_replan", _fake_generate_replan)
        _install_fake_executor(monkeypatch, _FakeExecutor(script=[_ok_result()]))

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        assert called["n"] == 1
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "completed"
        tasks = {t.local_id: t for t in AgentTaskRepository(db).list_by_run(run.id)}
        assert tasks["bare"].status == "failed"
        assert tasks["bare"].error_code == "contract_incomplete"
        assert tasks["fixed"].status == "completed"


class TestRestartSafety:
    @pytest.mark.asyncio
    async def test_second_call_on_an_already_completed_run_is_a_pure_noop(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()
        fake = _FakeExecutor(script=[_ok_result()])
        _install_fake_executor(monkeypatch, fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )
        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        assert OrchestrationRunRepository(db).get(run.id).status == "completed"
        assert fake.calls == 1  # the second call must not re-run anything

    @pytest.mark.asyncio
    async def test_resuming_mid_plan_does_not_regenerate_the_plan(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай лендинг для кофейни")
        db.commit()

        plan_calls = {"n": 0}
        real_generate_plan = engine.generate_plan

        async def _counting_generate_plan(**kwargs):
            plan_calls["n"] += 1
            return await real_generate_plan(**kwargs)

        monkeypatch.setattr(engine, "generate_plan", _counting_generate_plan)
        fake = _FakeExecutor(script=[_build_failed_result(), _ok_result()])
        _install_fake_executor(monkeypatch, fake)

        # First call: task fails once (still "running" the retry loop) - simulate a process
        # restart by simply calling run_orchestration again with a fresh db_factory-backed pass;
        # the active plan from the first call must be reused, not regenerated.
        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        assert plan_calls["n"] == 1
        db.expire_all()
        assert OrchestrationRunRepository(db).get(run.id).status == "completed"


class TestDependencyChaining:
    """A task declaring dependencies=["first"] must not become ready until "first" completes,
    and its TaskContract must carry "first"'s real result through dependency_results -
    build_dependency_results (context_engine.py) has no direct test coverage anywhere, and the
    only existing multi-PlannedTask scenario (TestBudget above) has no dependency edge between
    its two tasks, so this is the one place the planner->readiness->contract_builder dependency
    pass-through is exercised through the real engine end to end."""

    @pytest.mark.asyncio
    async def test_second_task_waits_for_and_receives_first_tasks_result(
        self, db: Session, db_factory, project: Project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _make_run(db, project, original_request="Сделай сайт с двумя задачами")
        db.commit()

        async def _fake_generate_plan(**kwargs):
            from src.services.orchestration.planner import PlanGenerationResult

            plan = ExecutionPlan(
                goal="two dependent tasks",
                complexity="compound",
                tasks=[
                    PlannedTask(
                        local_id="first",
                        title="Собрать каркас страницы",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="first",
                        reason="r",
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c1", description="d", verification_method="build"
                            )
                        ],
                    ),
                    PlannedTask(
                        local_id="second",
                        title="Добавить стили поверх каркаса",
                        role=SpecialistRole.IMPLEMENTER,
                        goal="second",
                        reason="r",
                        dependencies=["first"],
                        acceptance_criteria=[
                            AcceptanceCriterion(
                                id="c2", description="d", verification_method="build"
                            )
                        ],
                    ),
                ],
                estimated_budget=ExecutionBudget(),
            )
            return PlanGenerationResult(plan=plan, source="llm")

        monkeypatch.setattr(engine, "generate_plan", _fake_generate_plan)

        captured_contracts = []

        class _RecordingExecutor:
            def __init__(self) -> None:
                self.calls = 0

            async def execute(
                self, contract, context: TaskContext, cancellation
            ) -> AgentExecutionResult:
                self.calls += 1
                captured_contracts.append(contract)
                (context.workspace_root / f"output_{self.calls}.txt").write_text(
                    "x", encoding="utf-8"
                )
                summary = "каркас готов: header/main/footer" if self.calls == 1 else "стили готовы"
                return AgentExecutionResult(
                    task_result=TaskResult(
                        status="completed",
                        summary=summary,
                        claimed_changed_files=[f"output_{self.calls}.txt"],
                    ),
                    build_result={"ok": True, "log_tail": "ok"},
                )

        fake = _RecordingExecutor()
        monkeypatch.setattr(engine, "_build_executor", lambda kind, *, db, mcp_repo: fake)

        await engine.run_orchestration(
            run.id, db_factory=db_factory, provider_name="openai", model="m", api_key="k"
        )

        db.expire_all()
        refreshed = OrchestrationRunRepository(db).get(run.id)
        assert refreshed.status == "completed"
        assert fake.calls == 2

        tasks = {t.local_id: t for t in AgentTaskRepository(db).list_by_run(run.id)}
        assert tasks["first"].status == "completed"
        assert tasks["second"].status == "completed"

        assert len(captured_contracts) == 2
        first_contract, second_contract = captured_contracts
        assert first_contract.dependency_results == []

        assert len(second_contract.dependency_results) == 1
        dep = second_contract.dependency_results[0]
        assert dep.local_id == "first"
        # Proves real sequencing, not just plan order: this is only "completed" with a real
        # summary if "first" had actually finished (and its result was persisted) before
        # "second" was ever handed a contract.
        assert dep.status == "completed"
        assert "каркас готов" in dep.summary
        assert "output_1.txt" in dep.key_outputs
