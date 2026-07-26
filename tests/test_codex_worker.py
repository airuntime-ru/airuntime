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
