import asyncio
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from tests.conftest import TestingSessionLocal

from src.db.models.chat import Chat
from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.db.models.user import User
from src.db.models.workspace_lease import WorkspaceLease
from src.services import deployments
from src.services.agent import codex_worker
from src.services.orchestration import engine, events_bus
from src.services.orchestration.cancellation import CancellationToken
from src.services.orchestration.lease_heartbeat import LeaseHeartbeat, WorkspaceLeaseLost
from src.services.orchestration.repository import OrchestrationRunRepository, RunEventRepository
from src.services.orchestration.workspace_isolation import (
    AcquiredWorkspace,
    WorkspaceIsolationManager,
)
from src.workers import deployment_worker


def make_run(db):
    user = User(email=f"audit-{uuid.uuid4().hex}@example.com")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="Regression", type="website")
    db.add(project)
    db.flush()
    chat = Chat(project_id=project.id)
    db.add(chat)
    db.flush()
    run = OrchestrationRunRepository(db).create(
        project_id=project.id, user_id=user.id, chat_id=chat.id
    )
    return project, run


def test_expired_queued_codex_job_never_starts_a_container(monkeypatch):
    from unittest.mock import Mock

    redis = Mock()
    execute = Mock()
    monkeypatch.setattr(codex_worker, "_redis", lambda: redis)
    monkeypatch.setattr(codex_worker, "iter_codex_events", execute)
    codex_worker.execute_codex_run({"job_id": "expired", "deadline_epoch": 1})
    execute.assert_not_called()
    payload = json.loads(redis.rpush.call_args_list[0].args[1])
    assert payload["type"] == "infra_error"
    assert redis.rpush.call_args_list[-1].args[1] == codex_worker._DONE_MARKER


@pytest.mark.parametrize(
    "images", [[], ["/workspace/a.png"], ["/workspace/a.png", "/workspace/b.png"]]
)
def test_cli_prompt_is_separated_from_variadic_images(images):
    argv = codex_worker._build_argv(
        {"image_paths": images, "prompt": "--not-an-option"},
        model="test",
        remapped_cwd="/workspace",
    )
    assert argv[-2:] == ["--", "--not-an-option"]
    assert argv.count("--image") == len(images)


def test_rollback_does_not_publish_ghost_event(ensure_tables):
    db = TestingSessionLocal()
    _, run = make_run(db)
    db.commit()
    run_id = run.id
    sub = events_bus.get_event_bus().subscribe(str(run_id))
    try:
        events_bus.emit(db, run_id=run.id, event_type="task_started", payload={})
        assert sub.queue.empty()
        db.rollback()
        assert sub.queue.empty()
        assert RunEventRepository(db).list_since(run_id) == []
    finally:
        events_bus.get_event_bus().unsubscribe(str(run_id), sub)
        db.close()


def test_savepoint_commit_is_not_published_before_outer_commit(db):
    _, run = make_run(db)
    db.commit()
    sub = events_bus.get_event_bus().subscribe(str(run.id))
    try:
        with db.begin_nested():
            events_bus.emit(db, run_id=run.id, event_type="task_started", payload={})
        assert sub.queue.empty()
        db.commit()
        assert sub.queue.get_nowait()["event_type"] == "task_started"
    finally:
        events_bus.get_event_bus().unsubscribe(str(run.id), sub)


def test_concurrent_event_writers_get_unique_ordered_sequences(ensure_tables):
    db = TestingSessionLocal()
    _, run = make_run(db)
    db.commit()
    run_id = run.id
    barrier = threading.Barrier(2)

    def append(index):
        session = TestingSessionLocal()
        try:
            barrier.wait(timeout=5)
            row = RunEventRepository(session).append(
                run_id=run_id, event_type="trace", payload_json=json.dumps({"index": index})
            )
            seq = row.seq
            session.commit()
            return seq
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(append, range(2))) == [1, 2]
    finally:
        db.close()


def test_deployment_is_queued_only_once_for_a_run(db, monkeypatch):
    project, run = make_run(db)
    calls = []
    monkeypatch.setattr(deployments, "enqueue_deployment", lambda **kw: calls.append(kw) or True)
    monkeypatch.setattr(deployments, "assert_can_start_project", lambda *a, **kw: None)
    first = deployments.create_deployment_for_project(db, project, source_run_id=run.id)
    second = deployments.create_deployment_for_project(db, project, source_run_id=run.id)
    assert first.id == second.id
    assert len(calls) == 1
    assert db.query(Deployment).filter(Deployment.source_run_id == run.id).count() == 1


def test_expired_owner_cannot_commit_or_discard_another_owners_files(db, tmp_path):
    project, run = make_run(db)
    lease = WorkspaceLease(
        project_id=project.id,
        run_id=run.id,
        holder="old",
        mode="shared",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db.add(lease)
    db.flush()
    acquired = AcquiredWorkspace(
        mode="shared", workspace_root=tmp_path, project_root=tmp_path, lease=lease
    )
    with pytest.raises(WorkspaceLeaseLost):
        WorkspaceIsolationManager(db).assert_owned(acquired)


@pytest.mark.asyncio
async def test_heartbeat_renews_and_stops_with_task(monkeypatch):
    token = CancellationToken()
    heartbeat = LeaseHeartbeat(lambda: None, token, 3)
    heartbeat.interval = 0.01
    acquired = SimpleNamespace(lease=SimpleNamespace(id=uuid.uuid4(), holder="owner"))
    calls = []
    monkeypatch.setattr(heartbeat, "_renew", lambda *args: calls.append(args) or True)
    async with heartbeat:
        heartbeat.watch(acquired)
        await asyncio.sleep(0.04)
    count = len(calls)
    assert count > 0
    await asyncio.sleep(0.02)
    assert len(calls) == count
    assert not token.is_cancelled


@pytest.mark.asyncio
async def test_lost_heartbeat_cancels_execution(monkeypatch):
    token = CancellationToken()
    heartbeat = LeaseHeartbeat(lambda: None, token, 3)
    heartbeat.interval = 0.01
    monkeypatch.setattr(heartbeat, "_renew", lambda *args: False)
    async with heartbeat:
        heartbeat.watch(SimpleNamespace(lease=SimpleNamespace(id=uuid.uuid4(), holder="owner")))
        await asyncio.wait_for(token.wait(), timeout=1)
    assert "lease lost" in token.reason


@pytest.mark.parametrize(
    "verdict,critical,major,expected",
    [
        ("pass", 0, 0, "pass"),
        ("revise", 0, 0, "warnings"),
        ("blocked", 0, 0, "blocked"),
        ("revise", 1, 0, "blocked"),
        ("revise", 0, 1, "blocked"),
    ],
)
def test_final_quality_does_not_hide_blockers(verdict, critical, major, expected):
    task = SimpleNamespace(
        sequence=1,
        role="qa_reviewer",
        status="completed",
        skill_id="visual_preview_review",
        local_id="qa",
        result_json=json.dumps(
            {
                "review_verdict": verdict,
                "review_critical_count": critical,
                "review_major_count": major,
            }
        ),
    )
    assert engine._final_review_quality([task]) == expected


def test_worker_defers_jobs_at_capacity_instead_of_starting_unbounded_threads(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    queued = []
    monkeypatch.setattr(deployment_worker, "_codex_slots", slots)
    monkeypatch.setattr(deployment_worker, "requeue_control_job", queued.append)
    monkeypatch.setattr(deployment_worker.time, "sleep", lambda _: None)
    deployment_worker._spawn_codex_run({"job_id": "deferred"})
    assert queued == [{"job_id": "deferred"}]


@pytest.mark.asyncio
async def test_native_review_schema_is_closed_and_required(monkeypatch):
    from src.services.agent import pipeline_llm
    from src.services.agent.pipeline_models import ReviewResult

    observed = []

    async def complete(**kwargs):
        observed.append(kwargs["output_schema"])
        return ReviewResult(verdict="pass").model_dump_json()

    monkeypatch.setattr(pipeline_llm, "_raw_complete", complete)
    assert await pipeline_llm.complete_structured(
        provider_name="openai",
        model="test",
        api_key="test",
        system_prompt="test",
        user_text="test",
        response_model=ReviewResult,
    )
    schema = observed[0]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["$defs"]["ReviewScore"]["additionalProperties"] is False


def test_second_review_replaces_only_its_own_skill_verdict():
    def task(sequence, skill, verdict):
        return SimpleNamespace(
            sequence=sequence,
            role="qa_reviewer",
            status="completed",
            skill_id=skill,
            local_id=str(sequence),
            result_json=json.dumps({"review_verdict": verdict}),
        )

    assert (
        engine._final_review_quality(
            [task(1, "visual_preview_review", "blocked"), task(2, "visual_preview_review", "pass")]
        )
        == "pass"
    )
    assert (
        engine._final_review_quality(
            [task(1, "product_quality_review", "blocked"), task(2, "visual_preview_review", "pass")]
        )
        == "blocked"
    )


def test_fencing_prevents_stale_abort_from_discarding_files(db, tmp_path):
    from src.services.orchestration.git_transaction import GitTransactionManager

    project, run = make_run(db)
    lease = WorkspaceLease(
        project_id=project.id,
        run_id=run.id,
        holder="stale",
        mode="shared",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db.add(lease)
    db.flush()
    acquired = AcquiredWorkspace(
        mode="shared", workspace_root=tmp_path, project_root=tmp_path, lease=lease
    )
    path = tmp_path / "work.txt"
    path.write_text("new owner's work")
    handle = SimpleNamespace(acquired=acquired)
    with pytest.raises(WorkspaceLeaseLost):
        GitTransactionManager(db, WorkspaceIsolationManager(db)).abort(handle)
    assert path.read_text() == "new owner's work"


def test_heartbeat_renews_only_a_live_owned_lease(ensure_tables):
    session = TestingSessionLocal()
    project, run = make_run(session)
    lease = WorkspaceLease(
        project_id=project.id,
        run_id=run.id,
        holder="live-owner",
        mode="shared",
        expires_at=datetime.now(UTC) + timedelta(seconds=30),
    )
    session.add(lease)
    session.commit()
    lease_id = lease.id
    heartbeat = LeaseHeartbeat(TestingSessionLocal, CancellationToken(), 180)
    try:
        assert heartbeat._renew(lease_id, "live-owner")
        session.refresh(lease)
        assert lease.expires_at > datetime.now(UTC) + timedelta(seconds=150)
        assert not heartbeat._renew(lease_id, "another-owner")
        lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        assert not heartbeat._renew(lease_id, "live-owner")
    finally:
        session.close()
