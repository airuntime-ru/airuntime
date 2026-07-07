from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.api.dto.deployment import DeploymentResponse
from src.core.config import settings
from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.db.models.user import User
from src.db.session import get_db
from src.services.deployment_queue import enqueue_deployment
from src.workers.deployment_worker import process_job

router = APIRouter(prefix="/projects/{project_id}/deployments", tags=["deployments"])


@router.get("", response_model=list[DeploymentResponse])
def list_deployments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Deployment]:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return (
        db.query(Deployment)
        .filter(Deployment.project_id == project_id)
        .order_by(Deployment.started_at.desc())
        .all()
    )


@router.post("", response_model=DeploymentResponse)
def create_deployment(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    image_ref = settings.deployment_default_image
    deployment = Deployment(
        project_id=project.id,
        status="queued",
        image_ref=image_ref,
        container_id=None,
        logs_ref=None,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    job = {
        "deployment_id": str(deployment.id),
        "project_id": str(project.id),
        "image_ref": image_ref,
    }
    queued = enqueue_deployment(
        deployment_id=job["deployment_id"],
        project_id=job["project_id"],
        image_ref=job["image_ref"],
    )
    if not queued:
        process_job(job)
        db.refresh(deployment)
    return deployment
