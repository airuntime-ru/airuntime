from uuid import uuid4

import pytest

from src.db.models.project import Project
from src.db.models.user import User
from src.services.project_runtime import (
    RunningProjectLimitError,
    assert_can_start_project,
    count_running_projects,
    start_project_runtime,
    stop_project_runtime,
)
from tests.conftest import auth_tokens


class _FakeDockerAdapter:
    def __init__(self) -> None:
        self.stopped: list[str] = []

    def stop_project(self, project_id: str) -> None:
        self.stopped.append(project_id)


def _user(db, email: str, client) -> User:
    auth_tokens(client, email)
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    return user


def _project(db, user: User, *, name: str, status: str) -> Project:
    project = Project(
        id=uuid4(),
        user_id=user.id,
        type="website",
        name=name,
        description="",
        status=status,
    )
    db.add(project)
    db.flush()
    return project


def test_count_running_projects_includes_live_and_deploying(client, db):
    user = _user(db, "count-running@test.com", client)
    _project(db, user, name="live", status="live")
    _project(db, user, name="deploying", status="deploying")
    _project(db, user, name="stopped", status="stopped")
    db.commit()

    assert count_running_projects(db, user.id) == 2


def test_assert_can_start_project_raises_at_limit(client, db):
    user = _user(db, "assert-limit@test.com", client)
    for index in range(3):
        _project(db, user, name=f"live-{index}", status="live")
    db.commit()

    with pytest.raises(RunningProjectLimitError) as exc_info:
        assert_can_start_project(db, user.id)

    assert exc_info.value.limit == 3
    assert exc_info.value.running == 3


def test_stop_project_runtime_sets_stopped(client, db, monkeypatch):
    user = _user(db, "stop-runtime@test.com", client)
    project = _project(db, user, name="site", status="live")
    db.commit()

    fake = _FakeDockerAdapter()
    monkeypatch.setattr(
        "src.services.project_runtime.DockerDeploymentAdapter",
        lambda: fake,
    )

    stopped = stop_project_runtime(db, project)

    assert stopped.status == "stopped"
    assert fake.stopped == [str(project.id)]


def test_start_project_runtime_queues_deploy_when_slot_available(client, db, monkeypatch):
    user = _user(db, "start-runtime@test.com", client)
    project = _project(db, user, name="site", status="stopped")
    db.commit()
    queued: list[str] = []

    def fake_create_deployment(db_session, current_project):
        queued.append(str(current_project.id))
        current_project.status = "deploying"
        db_session.add(current_project)
        db_session.commit()
        return None

    monkeypatch.setattr(
        "src.services.deployments.create_deployment_for_project",
        fake_create_deployment,
    )

    started = start_project_runtime(db, project)

    assert queued == [str(project.id)]
    assert started.status == "deploying"


def test_runtime_limits_endpoint(client, db):
    headers = auth_tokens(client, "runtime-limits@airuntime.dev")
    user = _user(db, "runtime-limits@airuntime.dev", client)
    _project(db, user, name="one", status="live")
    _project(db, user, name="two", status="deploying")
    db.commit()

    response = client.get("/api/v1/projects/runtime-limits", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"running": 2, "max_running": 3}


def test_start_project_endpoint_returns_conflict_when_limit_reached(client, db):
    headers = auth_tokens(client, "runtime-conflict@airuntime.dev")
    user = _user(db, "runtime-conflict@airuntime.dev", client)
    for index in range(3):
        _project(db, user, name=f"live-{index}", status="live")
    stopped = _project(db, user, name="stopped", status="stopped")
    db.commit()

    response = client.post(f"/api/v1/projects/{stopped.id}/start", headers=headers)

    assert response.status_code == 409
    assert "лимит" in response.json()["detail"].lower()


def test_stop_project_endpoint(client, db, monkeypatch):
    headers = auth_tokens(client, "runtime-stop@airuntime.dev")
    user = _user(db, "runtime-stop@airuntime.dev", client)
    project = _project(db, user, name="live", status="live")
    db.commit()

    monkeypatch.setattr(
        "src.services.project_runtime.DockerDeploymentAdapter",
        lambda: _FakeDockerAdapter(),
    )

    response = client.post(f"/api/v1/projects/{project.id}/stop", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
