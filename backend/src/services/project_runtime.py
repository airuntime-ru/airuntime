from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.services.deployment.docker_adapter import DockerDeploymentAdapter


class RunningProjectLimitError(RuntimeError):
    def __init__(self, running: int, limit: int) -> None:
        self.running = running
        self.limit = limit
        super().__init__(
            f"Достигнут лимит одновременно запущенных проектов ({limit}). "
            "Остановите один из активных проектов, чтобы запустить новый."
        )


RUNNING_STATUSES = frozenset({"live", "deploying"})


def count_running_projects(
    db: Session, user_id: UUID, *, exclude_project_id: UUID | None = None
) -> int:
    query = db.query(Project).filter(
        Project.user_id == user_id,
        Project.status.in_(tuple(RUNNING_STATUSES)),
    )
    if exclude_project_id is not None:
        query = query.filter(Project.id != exclude_project_id)
    return query.count()


def assert_can_start_project(
    db: Session, user_id: UUID, *, exclude_project_id: UUID | None = None
) -> None:
    limit = settings.max_running_projects_per_user
    running = count_running_projects(db, user_id, exclude_project_id=exclude_project_id)
    if running >= limit:
        raise RunningProjectLimitError(running=running, limit=limit)


def _cancel_active_deployments(db: Session, project_id: UUID) -> None:
    active = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(("queued", "running")),
        )
        .all()
    )
    now = datetime.now(UTC)
    for deployment in active:
        deployment.status = "cancelled"
        deployment.finished_at = now
        db.add(deployment)


def stop_project_runtime(db: Session, project: Project) -> Project:
    if project.status not in RUNNING_STATUSES:
        raise ValueError("Проект не запущен")

    DockerDeploymentAdapter().stop_project(str(project.id))
    _cancel_active_deployments(db, project.id)
    project.status = "stopped"
    note = "Проект остановлен пользователем."
    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def block_project(db: Session, project: Project, *, reason: str) -> Project:
    try:
        DockerDeploymentAdapter().stop_project(str(project.id))
    except Exception:  # noqa: BLE001 - blocking must succeed even if Docker is unreachable
        pass
    _cancel_active_deployments(db, project.id)
    project.status = "blocked"
    project.blocked_reason = reason
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def start_project_runtime(db: Session, project: Project) -> Project:
    if project.status in RUNNING_STATUSES:
        raise ValueError("Проект уже запущен или запускается")

    # Import here to avoid circular imports.
    from src.services.deployments import create_deployment_for_project

    assert_can_start_project(db, project.user_id, exclude_project_id=project.id)
    project.status = "deploying"
    db.add(project)
    db.commit()
    db.refresh(project)
    create_deployment_for_project(db, project)
    db.refresh(project)
    return project
