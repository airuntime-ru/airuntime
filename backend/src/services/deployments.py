from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.services.deployment_queue import enqueue_deployment
from src.services.project_runtime import assert_can_start_project, cancel_active_deployments

# Must fit Deployment.logs_ref String(512).
_LOGS_REF_MAX = 500


def create_deployment_for_project(
    db: Session, project: Project, *, skip_auto_check: bool = False
) -> Deployment:
    assert_can_start_project(db, project.user_id, exclude_project_id=project.id)
    # One active build per project - otherwise users end up with multiple stuck "running" rows.
    cancel_active_deployments(db, project.id)
    # Always mark deploying (including redeploy from live) so the UI never shows "live"
    # while a new build is in flight.
    project.status = "deploying"
    db.add(project)
    db.commit()
    db.refresh(project)

    now = datetime.now(UTC)
    deployment = Deployment(
        project_id=project.id,
        status="queued",
        image_ref=None,
        container_id=None,
        logs_ref=None,
        # Used as queue timestamp so the worker can reap stuck queued jobs.
        started_at=now,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    job = {
        "deployment_id": str(deployment.id),
        "project_id": str(project.id),
        "image_ref": None,
        "skip_auto_check": skip_auto_check,
    }
    queued = enqueue_deployment(
        deployment_id=job["deployment_id"],
        project_id=job["project_id"],
        image_ref=None,
        skip_auto_check=skip_auto_check,
    )
    if not queued:
        # Lazy import: worker imports truncate_logs_ref from this module.
        from src.workers.deployment_worker import process_job

        process_job(job)
        db.refresh(deployment)
    return deployment


def truncate_logs_ref(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= _LOGS_REF_MAX:
        return cleaned
    return cleaned[: _LOGS_REF_MAX - 3] + "..."
