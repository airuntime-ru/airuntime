import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.db.models.project_service import ProjectService
from src.db.session import SessionLocal
from src.services.artifacts import build_project_image
from src.services.billing import run_billing_maintenance
from src.services.cloudflare_dns import CloudflareDnsError, sync_dns_for_website_deploy
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter
from src.services.deployment_check import (
    check_and_repair_deployment,
    detect_runtime_errors,
    is_repairable_app_error,
)
from src.services.deployment_queue import pop_deployment_job
from src.services.deployments import append_deployment_log, store_deployment_error, truncate_logs_ref
from src.services.docker_control_actions import run_control_action
from src.services.docker_control_queue import pop_control_job, push_control_result, worker_inline_docker
from src.services.project_services import (
    build_connection_env,
    ensure_service_containers,
)
from src.services.project_subdomain import resolve_deploy_subdomain
from src.services.telegram_profile import TelegramProfileError, fetch_bot_profile

BILLING_SWEEP_INTERVAL_SECONDS = 300
STALE_SWEEP_INTERVAL_SECONDS = 60


def process_billing_sweep() -> None:
    db: Session = SessionLocal()
    try:
        run_billing_maintenance(db)
    finally:
        db.close()


def process_control_job(job: dict) -> None:
    job_id = job.get("job_id", "")
    action = job.get("action")
    project_id = job.get("project_id")
    # Drop Redis envelope keys so run_control_action only sees action-specific extras.
    extra = {
        key: value
        for key, value in job.items()
        if key not in {"job_id", "action", "project_id"}
    }
    with worker_inline_docker():
        result = run_control_action(action=action, project_id=project_id, extra=extra)
    push_control_result(job_id, result)


def process_job(job: dict) -> None:
    db: Session = SessionLocal()
    with worker_inline_docker():
        _process_job_body(db, job)


def _process_job_body(db: Session, job: dict) -> None:
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

        deployment.status = "running"
        deployment.started_at = datetime.now(UTC)
        append_deployment_log(deployment, "Запуск сборки…\n")
        db.add(deployment)
        db.commit()

        def _on_build_log(chunk: str) -> None:
            # Flush live build output so the deployments page can poll log_text.
            append_deployment_log(deployment, chunk)
            db.add(deployment)
            try:
                db.commit()
            except Exception:  # noqa: BLE001 - never fail the build because of log flush
                db.rollback()

        image_ref, environment = build_project_image(db, project, on_log=_on_build_log)
        append_deployment_log(deployment, "\nОбраз собран. Запускаю контейнер…\n")
        db.add(deployment)
        db.commit()
        subdomain = resolve_deploy_subdomain(project)
        has_website = project.type in ("website", "mixed")
        has_bot = project.type in ("telegram_bot", "mixed")
        expose_http = has_website
        telegram_url = None
        if has_bot:
            token = environment.get("TELEGRAM_BOT_TOKEN")
            if not token:
                raise RuntimeError("Telegram bot token is not configured")
            try:
                telegram_url = fetch_bot_profile(token).public_url
            except TelegramProfileError as telegram_exc:
                raise RuntimeError(str(telegram_exc)) from telegram_exc

        adapter = DockerDeploymentAdapter()
        services = db.query(ProjectService).filter(ProjectService.project_id == project.id).all()
        service_network = None
        if services:
            service_network = adapter.ensure_private_network(str(project.id))
            ensure_service_containers(adapter.client, str(project.id), services)
            environment.update(build_connection_env(db, project))

        result = adapter.deploy(
            DeployRequest(
                project_id=str(project.id),
                image_ref=image_ref,
                subdomain=subdomain,
                environment=environment,
                expose_http=expose_http,
                service_network=service_network,
            )
        )

        # Confirm the process stays up after start - "docker run succeeded" is not enough
        # (bots/sites often crash on first import or missing env within a few seconds).
        append_deployment_log(deployment, "Контейнер создан. Проверяю, что процесс не падает…\n")
        db.add(deployment)
        db.commit()
        startup_logs = adapter.verify_still_running(result["container_id"], settle_seconds=5.0)
        startup_error = detect_runtime_errors(startup_logs)
        if startup_error:
            append_deployment_log(deployment, f"\n{startup_error[-8000:]}\n")
            try:
                adapter.stop_project(str(project.id))
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(
                "Контейнер запустился, но сразу выдал ошибку в runtime-логах:\n"
                f"{startup_error[-8000:]}"
            )

        append_deployment_log(deployment, "Контейнер стабилен после старта.\n")
        deployment.status = "completed"
        deployment.container_id = result["container_id"]
        deployment.logs_ref = result["logs_ref"]
        deployment.error_text = None
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
        if has_website and has_bot and telegram_url:
            # deployment_url holds the site's public link (the primary "open project" link) -
            # the bot's own link has nowhere else to live yet, so it goes into the log feed.
            bot_note = f"Telegram-бот доступен: {telegram_url}"
            project.logs = f"{project.logs}\n{bot_note}".strip() if project.logs else bot_note
        db.add(project)
        db.commit()

        if not job.get("skip_auto_check"):
            # Extra pass after we already verified the container stayed up: catches errors that
            # only appear slightly later. Manual "Проверить и исправить" covers user-triggered bugs.
            try:
                check_and_repair_deployment(db, project)
            except Exception:  # noqa: BLE001 - a broken self-check must never fail the deploy
                pass
    except Exception as exc:
        _mark_deployment_failed(db, job, exc)
    finally:
        db.close()


def _mark_deployment_failed(db: Session, job: dict, exc: BaseException) -> None:
    """Always terminalize the deployment row, even if logging the error is awkward."""
    deployment = db.get(Deployment, job.get("deployment_id"))
    if not deployment:
        return
    full_error = str(exc)
    try:
        deployment.status = "failed"
        store_deployment_error(deployment, full_error)
        deployment.finished_at = datetime.now(UTC)
        project = db.get(Project, job.get("project_id"))
        if project and project.status in {"deploying", "live"}:
            # Generic deploy failure is not "needs secrets" - leave that for missing tokens.
            project.status = "ready"
            note = f"Deployment failed: {truncate_logs_ref(full_error)}"
            project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
            db.add(project)
        db.add(deployment)
        db.commit()
    except Exception:  # noqa: BLE001 - last-resort hard fail without long logs_ref
        db.rollback()
        deployment = db.get(Deployment, job.get("deployment_id"))
        if not deployment:
            return
        deployment.status = "failed"
        deployment.logs_ref = "Deployment failed (see worker logs)"
        deployment.error_text = full_error[:50_000] if full_error else "Deployment failed"
        deployment.finished_at = datetime.now(UTC)
        project = db.get(Project, job.get("project_id"))
        if project and project.status in {"deploying", "live"}:
            project.status = "ready"
            db.add(project)
        db.add(deployment)
        db.commit()
        return

    project = db.get(Project, job.get("project_id"))
    if (
        project
        and not job.get("skip_auto_check")
        and is_repairable_app_error(full_error)
    ):
        try:
            # Pass the FULL error so repair is not limited to the 500-char logs_ref hint.
            # Runs under worker_inline_docker so build_project/logs do not self-deadlock.
            check_and_repair_deployment(db, project, force_error=full_error)
        except Exception:  # noqa: BLE001 - never crash the worker on repair failure
            pass


def reap_stale_deployments() -> int:
    """Mark queued/running deployments older than deployment_timeout_seconds as failed."""
    timeout = max(30, int(getattr(settings, "deployment_timeout_seconds", 120) or 120))
    cutoff = datetime.now(UTC) - timedelta(seconds=timeout)
    db: Session = SessionLocal()
    reaped = 0
    try:
        candidates = (
            db.query(Deployment)
            .filter(Deployment.status.in_(("queued", "running")))
            .all()
        )
        for deployment in candidates:
            # Null started_at = orphan from older code paths; treat as immediately stale.
            if deployment.started_at is not None and deployment.started_at >= cutoff:
                continue
            prior_status = deployment.status
            deployment.status = "failed"
            store_deployment_error(
                deployment,
                f"Deployment timed out after {timeout}s (stuck in {prior_status})",
            )
            deployment.finished_at = datetime.now(UTC)
            project = db.get(Project, deployment.project_id)
            if project and project.status == "deploying":
                # Only clear deploying if no other active deploy remains.
                other_active = (
                    db.query(Deployment)
                    .filter(
                        Deployment.project_id == project.id,
                        Deployment.id != deployment.id,
                        Deployment.status.in_(("queued", "running")),
                    )
                    .first()
                )
                if not other_active:
                    project.status = "ready"
                    note = f"Deployment timed out: {deployment.id}"
                    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
                    db.add(project)
            db.add(deployment)
            reaped += 1
        if reaped:
            db.commit()
    finally:
        db.close()
    return reaped


def run() -> None:
    last_billing_sweep = 0.0
    last_stale_sweep = 0.0
    try:
        reap_stale_deployments()
    except Exception:  # noqa: BLE001
        pass
    while True:
        control_job = pop_control_job(timeout_seconds=2)
        if control_job:
            try:
                process_control_job(control_job)
            except Exception:  # noqa: BLE001 - never kill the worker loop
                pass
            continue
        job = pop_deployment_job(timeout_seconds=2)
        if job:
            try:
                process_job(job)
            except Exception:  # noqa: BLE001 - process_job should self-contain, but belt+suspenders
                try:
                    db = SessionLocal()
                    try:
                        _mark_deployment_failed(db, job, RuntimeError("Worker crashed during deploy"))
                    finally:
                        db.close()
                except Exception:  # noqa: BLE001
                    pass

        now = time.monotonic()
        if now - last_stale_sweep >= STALE_SWEEP_INTERVAL_SECONDS:
            last_stale_sweep = now
            try:
                reap_stale_deployments()
            except Exception:  # noqa: BLE001
                pass
        if now - last_billing_sweep >= BILLING_SWEEP_INTERVAL_SECONDS:
            last_billing_sweep = now
            try:
                process_billing_sweep()
            except Exception:  # noqa: BLE001 - never let a billing hiccup kill the worker loop
                pass


if __name__ == "__main__":
    run()
