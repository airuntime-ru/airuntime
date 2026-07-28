from src.core.config import settings
from src.services.agent import codex_worker


class _FakeVolume:
    attrs = {"Mountpoint": "/var/lib/docker/volumes/airuntime/_data"}


class _FakeVolumes:
    def get(self, name: str) -> _FakeVolume:
        assert name == settings.generated_projects_volume_name
        return _FakeVolume()


class _FakeClient:
    volumes = _FakeVolumes()


class _FakeContainer:
    removed = False

    def remove(self, *, force: bool) -> None:
        assert force is True
        self.removed = True


class _FakeContainers:
    def __init__(self, container: _FakeContainer) -> None:
        self.container = container

    def get(self, name: str) -> _FakeContainer:
        assert name == "airuntime-codex-job-1"
        return self.container


class _FakeCleanupClient:
    def __init__(self, container: _FakeContainer) -> None:
        self.containers = _FakeContainers(container)


def test_resolve_workspace_mount_preserves_shared_project_path() -> None:
    result = codex_worker._resolve_workspace_mount(
        _FakeClient(), "/data/airruntime-projects/project-1"
    )
    assert result == "/var/lib/docker/volumes/airuntime/_data/project-1"


def test_resolve_workspace_mount_preserves_isolated_worktree_path() -> None:
    result = codex_worker._resolve_workspace_mount(
        _FakeClient(),
        "/data/airruntime-projects/project-1__worktrees/task-1",
    )
    assert result == ("/var/lib/docker/volumes/airuntime/_data/project-1__worktrees/task-1")


def test_resolve_workspace_mount_rejects_path_outside_projects_volume() -> None:
    assert codex_worker._resolve_workspace_mount(_FakeClient(), "/etc") is None


def test_remove_failed_start_container_removes_created_container() -> None:
    container = _FakeContainer()

    codex_worker._remove_failed_start_container(
        _FakeCleanupClient(container), "airuntime-codex-job-1"
    )

    assert container.removed is True


def test_build_argv_uses_configured_reasoning_effort(monkeypatch) -> None:
    monkeypatch.setattr(settings, "codex_reasoning_effort", "max")

    argv = codex_worker._build_argv(
        {"prompt": "Build the project"},
        model="gpt-5.6-sol",
        remapped_cwd=None,
    )

    assert argv[argv.index("--model") + 1] == "gpt-5.6-sol"
    assert argv[argv.index("-c") + 1] == 'model_reasoning_effort="max"'


def test_visual_review_container_has_no_docker_access(monkeypatch) -> None:
    monkeypatch.setattr(settings, "codex_docker_host", "tcp://docker-proxy:2375")

    assert codex_worker._container_volumes(None, allow_docker=False) == {}
    env = codex_worker._container_env("key", "project-1", allow_docker=False)
    assert "DOCKER_HOST" not in env
    assert "DOCKER_BUILDKIT" not in env


def test_project_container_disables_buildkit_for_socket_proxy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "codex_docker_host", "tcp://docker-proxy:2375")

    env = codex_worker._container_env("key", "project-1", allow_docker=True)

    assert env["DOCKER_HOST"] == "tcp://docker-proxy:2375"
    assert env["DOCKER_BUILDKIT"] == "0"
