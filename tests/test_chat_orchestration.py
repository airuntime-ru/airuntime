"""Tests for chat.py's _orchestration_event_source - the only path a real chat message takes,
through the persistent orchestration engine. The engine's own correctness is exhaustively covered
elsewhere (test_orchestration_engine_e2e.py); this file only proves the *wiring*: a POST /stream
creates a real OrchestrationRun, drives it via the same launch_run_in_background seam the API
router uses, translates its events into the existing SSE {chunk}/{status} shape, reuses the
existing deploy pipeline on success, and persists the assistant reply.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session
from tests.conftest import TestingSessionLocal, auth_tokens

from src.api.routers import chat as chat_router
from src.core.config import settings
from src.db.models.orchestration_run import OrchestrationRun
from src.services import project_git, workspace
from src.services.orchestration import engine as orchestration_engine
from src.services.orchestration.executors import AgentExecutionResult
from src.services.orchestration.schemas import TaskResult


class _FakeExecutor:
    def __init__(self, result: AgentExecutionResult) -> None:
        self.result = result
        self.calls = 0

    async def execute(self, contract, context, cancellation) -> AgentExecutionResult:
        self.calls += 1
        public_dir = context.workspace_root / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        (public_dir / "index.html").write_text("<html>hi</html>", encoding="utf-8")
        return self.result


def _ok_result() -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(status="completed", summary="Готово"),
        build_result={"ok": True, "log_tail": "ok"},
    )


def _secret_result(key: str) -> AgentExecutionResult:
    return AgentExecutionResult(
        task_result=TaskResult(status="partial", summary="нужен ключ", requested_secrets=[key]),
        build_result=None,
    )


def _fake_live_deployment(db, project):
    from datetime import UTC, datetime

    from src.db.models.deployment import Deployment

    project.status = "live"
    if not project.deployment_url:
        project.deployment_url = "https://example.airuntime.ru"
    deployment = Deployment(
        project_id=project.id,
        status="completed",
        image_ref="test:latest",
        container_id="ctr-test",
        logs_ref=None,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db.add(project)
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))

    async def _fake_check_project_safety(**kwargs):
        from src.services.moderation import ModerationVerdict

        return ModerationVerdict(blocked=False)

    monkeypatch.setattr(chat_router, "check_project_safety", _fake_check_project_safety)


@pytest.fixture(autouse=True)
def _share_test_connection(monkeypatch: pytest.MonkeyPatch, db: Session):
    """Both chat.py's own SessionLocal reference and the one engine.launch_run_in_background
    closes over (a separate module) must resolve to a session sharing THIS test's connection/
    transaction - see test_orchestration_api.py's identical rationale."""

    def _factory() -> Session:
        return TestingSessionLocal(bind=db.get_bind())

    monkeypatch.setattr(chat_router, "SessionLocal", _factory)
    monkeypatch.setattr(orchestration_engine, "SessionLocal", _factory)


@pytest.fixture(autouse=True)
def _workspace_dir(monkeypatch: pytest.MonkeyPatch):
    """engine.py imports services.workspace.project_dir AS project_workspace_dir, so in
    production the engine and chat.py's own post-run checks resolve the exact same directory.
    This fixture must preserve that (sending them to different roots would make the deploy-gate
    backstop in _orchestration_event_source silently inspect an empty dir) - it only adds the
    git init the engine's first git transaction needs."""

    def _dir(project_id):
        root = workspace.project_dir(project_id)
        project_git.init_repo_if_needed(root)
        return root

    monkeypatch.setattr(orchestration_engine, "project_workspace_dir", _dir)


def _install_fake_executor(
    monkeypatch: pytest.MonkeyPatch, result: AgentExecutionResult
) -> _FakeExecutor:
    fake = _FakeExecutor(result)
    monkeypatch.setattr(orchestration_engine, "_build_executor", lambda kind, *, db, mcp_repo: fake)
    return fake


def _chunks(response) -> list[str]:
    # response.text is the raw SSE body - json.dumps(..., ensure_ascii=True) (chat.py's
    # _sse_chunk/_sse_status default) escapes Cyrillic to literal \uXXXX, so a Cyrillic
    # substring check must go through json.loads rather than matching response.text directly.
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    return [p["chunk"] for p in payloads if "chunk" in p]


def _create_project_and_chat(client, headers) -> tuple[str, str]:
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Orchestrated Site", "description": ""},
    ).json()
    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()
    return project["id"], chat["id"]


class TestOrchestrationEnabledHappyPath:
    def test_stream_drives_a_real_run_and_deploys(
        self, client, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        headers = auth_tokens(client, "chat-orch-happy@airuntime.dev")
        project_id, chat_id = _create_project_and_chat(client, headers)
        fake = _install_fake_executor(monkeypatch, _ok_result())
        monkeypatch.setattr(chat_router, "create_deployment_for_project", _fake_live_deployment)

        response = client.post(
            f"/api/v1/projects/{project_id}/chats/{chat_id}/stream",
            headers=headers,
            json={"content": "Сделай лендинг для кофейни"},
        )

        assert response.status_code == 200
        assert fake.calls == 1
        assert any("Сайт запущен" in chunk for chunk in _chunks(response))
        assert "data: [DONE]" in response.text

        db.expire_all()
        runs = db.query(OrchestrationRun).filter_by(project_id=uuid.UUID(project_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"

        messages = client.get(
            f"/api/v1/projects/{project_id}/chats/{chat_id}/messages", headers=headers
        ).json()
        assert any(
            "Сайт запущен" in m["content_markdown"] for m in messages if m["role"] == "assistant"
        )


class TestOrchestrationWaitingForSecret:
    def test_stream_surfaces_the_requested_secret_and_stops_cleanly(
        self, client, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        headers = auth_tokens(client, "chat-orch-secret@airuntime.dev")
        project_id, chat_id = _create_project_and_chat(client, headers)
        _install_fake_executor(monkeypatch, _secret_result("STRIPE_API_KEY"))

        response = client.post(
            f"/api/v1/projects/{project_id}/chats/{chat_id}/stream",
            headers=headers,
            json={"content": "Сделай сайт с оплатой"},
        )

        assert response.status_code == 200
        assert "STRIPE_API_KEY" in response.text
        assert "data: [DONE]" in response.text

        db.expire_all()
        from src.db.models.secret import Secret

        secret = (
            db.query(Secret)
            .filter(Secret.project_id == uuid.UUID(project_id), Secret.key == "STRIPE_API_KEY")
            .first()
        )
        assert secret is not None
        assert secret.encrypted_value is None
