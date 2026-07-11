from sqlalchemy.orm import Session

from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.services.deployment_queue import enqueue_deployment
from src.services.project_runtime import assert_can_start_project
from src.workers.deployment_worker import process_job


def create_deployment_for_project(
    db: Session, project: Project, *, skip_auto_check: bool = False
) -> Deployment:
    assert_can_start_project(db, project.user_id, exclude_project_id=project.id)
    if project.status not in {"live", "deploying"}:
        project.status = "deploying"
        db.add(project)
        db.commit()
        db.refresh(project)

    deployment = Deployment(
        project_id=project.id,
        status="queued",
        image_ref=None,
        container_id=None,
        logs_ref=None,
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
        process_job(job)
        db.refresh(deployment)
    return deployment
