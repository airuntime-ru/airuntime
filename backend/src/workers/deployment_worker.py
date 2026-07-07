from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.db.session import SessionLocal
from src.services.artifacts import build_project_image
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter, slugify
from src.services.deployment_queue import pop_deployment_job


def process_job(job: dict) -> None:
    db: Session = SessionLocal()
    try:
        deployment = db.get(Deployment, job["deployment_id"])
        if not deployment:
            return
        project = db.get(Project, job["project_id"])
        if not project:
            deployment.status = "failed"
            deployment.finished_at = datetime.now(UTC)
            db.commit()
            return

        deployment.status = "running"
        deployment.started_at = datetime.now(UTC)
        db.commit()

        image_ref, environment = build_project_image(db, project)
        subdomain = f"{slugify(project.name)}-{str(project.id)[:8]}"
        expose_http = project.type == "website"
        result = DockerDeploymentAdapter().deploy(
            DeployRequest(
                project_id=str(project.id),
                image_ref=image_ref,
                subdomain=subdomain,
                environment=environment,
                expose_http=expose_http,
            )
        )

        deployment.status = "completed"
        deployment.container_id = result["container_id"]
        deployment.logs_ref = result["logs_ref"]
        deployment.image_ref = result["image_ref"]
        deployment.finished_at = datetime.now(UTC)
        project.deployment_url = result["url"] if expose_http else "telegram-bot:polling"
        project.status = "live"
        db.add(project)
        db.commit()
    except Exception as exc:
        if deployment := db.get(Deployment, job.get("deployment_id")):
            deployment.status = "failed"
            deployment.logs_ref = str(exc)[:2000]
            deployment.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def run() -> None:
    while True:
        job = pop_deployment_job(timeout_seconds=10)
        if not job:
            continue
        process_job(job)


if __name__ == "__main__":
    run()
