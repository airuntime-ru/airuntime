from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tests.conftest import auth_tokens

from src.db.models.chat import Chat
from src.db.models.message import Message
from src.db.models.project import Project
from src.db.models.user import User
from src.workers import deployment_worker


class _FakeSessionWithGet:
    def __init__(self, project) -> None:
        self._project = project
        self.closed = False

    def get(self, model, id_):
        return self._project

    def close(self) -> None:
        self.closed = True


class _FakeAdapter:
    def __init__(self, stop_calls: list[str]) -> None:
        self._stop_calls = stop_calls
        self.client = object()

    def stop_project(self, project_id: str) -> None:
        self._stop_calls.append(project_id)


class _FakeQuery:
    def __init__(self, result) -> None:
        self._result = result

    def filter(self, *args, **kwargs) -> "_FakeQuery":
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, *, has_services: bool) -> None:
        self._has_services = has_services
        self.closed = False

    def query(self, model):
        return _FakeQuery(object() if self._has_services else None)

    def close(self) -> None:
        self.closed = True


def test_process_control_job_stop_leaves_services_alone(monkeypatch):
    stop_calls: list[str] = []
    teardown_calls: list[tuple] = []
    results: list[dict] = []

    monkeypatch.setattr(
        deployment_worker, "DockerDeploymentAdapter", lambda: _FakeAdapter(stop_calls)
    )
    monkeypatch.setattr(
        deployment_worker,
        "teardown_service_containers",
        lambda client, project_id, *, remove_volumes: teardown_calls.append(
            (project_id, remove_volumes)
        ),
    )
    monkeypatch.setattr(
        deployment_worker, "push_control_result", lambda job_id, result: results.append(result)
    )

    deployment_worker.process_control_job({"job_id": "j1", "action": "stop", "project_id": "p1"})

    assert stop_calls == ["p1"]
    assert teardown_calls == []
    assert results == [{"ok": True}]


def test_process_control_job_cleanup_tears_down_services(monkeypatch):
    stop_calls: list[str] = []
    teardown_calls: list[tuple] = []
    results: list[dict] = []

    monkeypatch.setattr(
        deployment_worker, "DockerDeploymentAdapter", lambda: _FakeAdapter(stop_calls)
    )
    monkeypatch.setattr(deployment_worker, "SessionLocal", lambda: _FakeSession(has_services=True))
    monkeypatch.setattr(
        deployment_worker,
        "teardown_service_containers",
        lambda client, project_id, *, remove_volumes: teardown_calls.append(
            (project_id, remove_volumes)
        ),
    )
    monkeypatch.setattr(
        deployment_worker, "push_control_result", lambda job_id, result: results.append(result)
    )

    deployment_worker.process_control_job({"job_id": "j2", "action": "cleanup", "project_id": "p1"})

    assert stop_calls == ["p1"]
    assert teardown_calls == [("p1", True)]
    assert results == [{"ok": True}]


def test_process_control_job_cleanup_skips_teardown_without_services(monkeypatch):
    stop_calls: list[str] = []
    teardown_calls: list[tuple] = []
    results: list[dict] = []

    monkeypatch.setattr(
        deployment_worker, "DockerDeploymentAdapter", lambda: _FakeAdapter(stop_calls)
    )
    monkeypatch.setattr(deployment_worker, "SessionLocal", lambda: _FakeSession(has_services=False))
    monkeypatch.setattr(
        deployment_worker,
        "teardown_service_containers",
        lambda client, project_id, *, remove_volumes: teardown_calls.append(
            (project_id, remove_volumes)
        ),
    )
    monkeypatch.setattr(
        deployment_worker, "push_control_result", lambda job_id, result: results.append(result)
    )

    deployment_worker.process_control_job({"job_id": "j3", "action": "cleanup", "project_id": "p1"})

    assert stop_calls == ["p1"]
    assert teardown_calls == []
    assert results == [{"ok": True}]


def test_notify_fallback_used_posts_message_to_latest_chat(client, db):
    auth_tokens(client, "fallback-notify@airuntime.dev")
    user = db.query(User).filter(User.email == "fallback-notify@airuntime.dev").first()
    project = Project(
        id=uuid4(), user_id=user.id, type="telegram_bot", name="Fallback Bot", description=""
    )
    db.add(project)
    db.flush()
    now = datetime.now(UTC)
    older_chat = Chat(
        project_id=project.id, title="First chat", created_at=now - timedelta(minutes=5)
    )
    newer_chat = Chat(project_id=project.id, title="Second chat", created_at=now)
    db.add(older_chat)
    db.flush()
    db.add(newer_chat)
    db.commit()

    deployment_worker._notify_fallback_used(db, project)
    db.commit()

    messages = db.query(Message).filter(Message.chat_id == newer_chat.id).all()
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert "заглушку" in messages[0].content_markdown

    assert db.query(Message).filter(Message.chat_id == older_chat.id).count() == 0


def test_notify_fallback_used_noop_without_any_chat(client, db):
    auth_tokens(client, "fallback-nochat@airuntime.dev")
    user = db.query(User).filter(User.email == "fallback-nochat@airuntime.dev").first()
    project = Project(
        id=uuid4(), user_id=user.id, type="telegram_bot", name="No Chat Bot", description=""
    )
    db.add(project)
    db.commit()

    deployment_worker._notify_fallback_used(db, project)  # should not raise
    db.commit()

    assert db.query(Message).count() == 0


def test_process_control_job_build_check_returns_build_result(monkeypatch):
    fake_project = object()
    monkeypatch.setattr(
        deployment_worker, "SessionLocal", lambda: _FakeSessionWithGet(fake_project)
    )
    build_calls: list = []
    monkeypatch.setattr(
        deployment_worker,
        "try_build_project_image",
        lambda project: build_calls.append(project) or {"ok": True, "log": "Build succeeded"},
    )
    results: list[dict] = []
    monkeypatch.setattr(
        deployment_worker, "push_control_result", lambda job_id, result: results.append(result)
    )

    deployment_worker.process_control_job(
        {"job_id": "j4", "action": "build_check", "project_id": "p1"}
    )

    assert build_calls == [fake_project]
    assert results == [{"ok": True, "log": "Build succeeded"}]


def test_process_control_job_build_check_missing_project(monkeypatch):
    monkeypatch.setattr(deployment_worker, "SessionLocal", lambda: _FakeSessionWithGet(None))
    results: list[dict] = []
    monkeypatch.setattr(
        deployment_worker, "push_control_result", lambda job_id, result: results.append(result)
    )

    deployment_worker.process_control_job(
        {"job_id": "j5", "action": "build_check", "project_id": "p1"}
    )

    assert results == [{"ok": False, "log": "Project not found"}]
