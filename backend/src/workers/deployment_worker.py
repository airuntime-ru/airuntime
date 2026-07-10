from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.db.session import SessionLocal
from src.services.artifacts import build_project_image
from src.services.cloudflare_dns import CloudflareDnsError, sync_dns_for_website_deploy
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter
from src.services.deployment_queue import pop_deployment_job
from src.services.docker_control_queue import pop_control_job, push_control_result
from src.services.project_subdomain import resolve_deploy_subdomain
from src.services.telegram_profile import TelegramProfileError, fetch_bot_profile


def process_control_job(job: dict) -> None:
    job_id = job.get("job_id", "")
    action = job.get("action")
    project_id = job.get("project_id")
    try:
        if action in ("stop", "cleanup") and project_id:
            DockerDeploymentAdapter().stop_project(str(project_id))
        push_control_result(job_id, {"ok": True})
    except Exception as exc:  # noqa: BLE001 - always report back, never crash the worker loop
        push_control_result(job_id, {"ok": False, "error": str(exc)})


def process_job(job: dict) -> None:
    db: Session = SessionLocal()
    try:
        deployment = db.get(Deployment, job["deployment_id"])
        if not deployment:
            return
        if deployment.status in {"cancelled", "stopped"}:
            return
        project = db.get(Project, job["project_id"])
        if not project:
            deployment.status = "failed"
            deployment.finished_at = datetime.now(UTC)
            db.commit()
            return
        if project.status == "stopped":
            deployment.status = "cancelled"
            deployment.finished_at = datetime.now(UTC)
            db.commit()
            return
        if project.status == "stopped":
            deployment.status = "cancelled"
            deployment.finished_at = datetime.now(UTC)
            db.commit()
            return

        deployment.status = "running"
        deployment.started_at = datetime.now(UTC)
        db.commit()

        image_ref, environment = build_project_image(db, project)
        subdomain = resolve_deploy_subdomain(project)
        expose_http = project.type == "website"
        telegram_url = None
        if project.type == "telegram_bot":
            token = environment.get("TELEGRAM_BOT_TOKEN")
            if not token:
                raise RuntimeError("Telegram bot token is not configured")
            try:
                telegram_url = fetch_bot_profile(token).public_url
            except TelegramProfileError as telegram_exc:
                raise RuntimeError(str(telegram_exc)) from telegram_exc

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
        db.refresh(project)
        if project.status == "stopped":
            DockerDeploymentAdapter().stop_project(str(project.id))
            deployment.status = "cancelled"
            deployment.finished_at = datetime.now(UTC)
            db.add(deployment)
            db.commit()
            return
        project.deployment_url = result["url"] if expose_http else telegram_url
        project.status = "live"
        if expose_http:
            try:
                dns_messages = sync_dns_for_website_deploy(subdomain)
                dns_note = "Cloudflare DNS: " + "; ".join(dns_messages)
                project.logs = f"{project.logs}\n{dns_note}".strip() if project.logs else dns_note
            except CloudflareDnsError as dns_exc:
                dns_note = f"Cloudflare DNS warning: {dns_exc}"
                project.logs = f"{project.logs}\n{dns_note}".strip() if project.logs else dns_note
        db.add(project)
        db.commit()
    except Exception as exc:
        if deployment := db.get(Deployment, job.get("deployment_id")):
            deployment.status = "failed"
            deployment.logs_ref = str(exc)[:2000]
            deployment.finished_at = datetime.now(UTC)
            if project := db.get(Project, job.get("project_id")):
                project.status = "needs_configuration"
                note = f"Deployment failed: {exc}"
                project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
                db.add(project)
            db.commit()
    finally:
        db.close()


def run() -> None:
    while True:
        control_job = pop_control_job(timeout_seconds=2)
        if control_job:
            process_control_job(control_job)
            continue
        job = pop_deployment_job(timeout_seconds=2)
        if not job:
            continue
        process_job(job)


if __name__ == "__main__":
    run()
