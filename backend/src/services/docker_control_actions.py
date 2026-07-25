"""Execute docker-control actions (same logic the worker uses for Redis RPCs).

Kept separate so the worker can run these inline while already handling a deploy —
otherwise repair agents that call build_project / logs would deadlock waiting for the
same single worker to pop its own control job.
"""

from __future__ import annotations

import logging
from typing import Any

from src.db.models.project import Project
from src.db.models.project_service import ProjectService
from src.db.session import SessionLocal
from src.services.artifacts import _telegram_token, try_build_project_image
from src.services.deployment.docker_adapter import DockerDeploymentAdapter, app_container_name
from src.services.preview_runner import _preview_network_name, run_preview
from src.services.project_services import build_connection_env, teardown_service_containers

logger = logging.getLogger(__name__)


def _run_runtime_health_check(project_id: str) -> dict[str, Any]:
    """Real runtime verification, closing the gap left by `verify_still_running`'s flat 5s
    sleep+status-check (docker_adapter.py) and deployment_check.py's pure log-regex scanning -
    neither of those does a restart-loop check or confirms the app is actually listening.

    `port_80_listening` is read from the container's own `/proc/net/tcp` via `exec_run` (state
    `0A` = TCP_LISTEN, local port `:0050` hex = 80 decimal) rather than an HTTP client
    (curl/wget) - deliberately, since a generated project's base image is never guaranteed to
    have either installed, but every Linux container has a `/proc` filesystem and a shell.
    This confirms *something* is listening on the platform's documented app port, not that it
    returns a healthy response - a real HTTP probe is a reasonable future enhancement, not
    something this change claims to already do.
    """
    adapter = DockerDeploymentAdapter()
    exact = app_container_name(project_id)
    matches = [
        c
        for c in adapter.client.containers.list(all=True, filters={"name": exact})
        if c.name == exact
    ]
    if not matches:
        return {"ok": False, "container_found": False, "reason": "no app container found"}

    container = matches[0]
    container.reload()
    state = container.attrs.get("State", {})
    restart_count = int(container.attrs.get("RestartCount", 0) or 0)
    restarting = bool(state.get("Restarting"))
    status = container.status
    # A single-digit restart count in isolation is normal (a slow-starting app crashing once
    # before its DB dependency is ready); >=3 within the container's current lifetime is the
    # conventional "probably crash-looping" threshold this platform uses.
    restart_loop_suspected = restart_count >= 3

    port_80_listening = False
    if status == "running":
        try:
            exec_result = container.exec_run(["sh", "-c", "cat /proc/net/tcp 2>/dev/null"])
            output = (exec_result.output or b"").decode("utf-8", errors="replace")
            for line in output.splitlines()[1:]:
                columns = line.split()
                if len(columns) >= 4 and columns[1].endswith(":0050") and columns[3] == "0A":
                    port_80_listening = True
                    break
        except Exception:  # noqa: BLE001 - a failed probe just means "not confirmed", not a crash
            logger.warning(
                "runtime_health_check: port probe failed for %s", project_id, exc_info=True
            )

    return {
        "ok": status == "running" and not restart_loop_suspected and port_80_listening,
        "container_found": True,
        "container_status": status,
        "restart_count": restart_count,
        "restarting": restarting,
        "restart_loop_suspected": restart_loop_suspected,
        "port_80_listening": port_80_listening,
    }


def _cancel_codex_run(correlation_id: str) -> dict[str, Any]:
    """Real `docker stop` for an in-flight Codex container, found by the deterministic name
    codex_worker.py gives it (`airuntime-codex-{job_id}`, job_id == correlation_id ==
    orchestration AgentTask.id - see codex_runtime.py's correlation_id). Not finding the
    container is reported as ok=True (not an error): the run may have already finished
    naturally between the cancel request being issued and this action executing, which is a
    race any cancel-a-possibly-already-done-thing operation has to tolerate gracefully."""
    client = DockerDeploymentAdapter().client
    name = f"airuntime-codex-{correlation_id}"
    try:
        container = client.containers.get(name)
    except Exception:  # noqa: BLE001 - docker.errors.NotFound is the expected case; any other
        # lookup failure is equally "nothing to stop" from this action's point of view
        return {"ok": True, "found": False}
    try:
        container.stop(timeout=5)
    except Exception:  # noqa: BLE001 - already stopped/removed between get() and stop() is fine
        pass
    return {"ok": True, "found": True}


def run_control_action(
    *, action: str | None, project_id: str | None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run one control action and return a result dict (ok=True/False, …)."""
    extra = extra or {}
    try:
        if action == "cancel_codex_run":
            correlation_id = extra.get("correlation_id")
            if not correlation_id:
                return {"ok": False, "error": "missing correlation_id"}
            return _cancel_codex_run(str(correlation_id))
        if action == "stop" and project_id:
            # App container only - sidecars stay up for a fast restart.
            DockerDeploymentAdapter().stop_project(str(project_id))
            return {"ok": True}
        if action == "cleanup" and project_id:
            adapter = DockerDeploymentAdapter()
            adapter.stop_project(str(project_id))
            adapter.remove_project_images(str(project_id))
            db = SessionLocal()
            try:
                has_services = (
                    db.query(ProjectService).filter(ProjectService.project_id == project_id).first()
                    is not None
                )
            finally:
                db.close()
            if has_services:
                teardown_service_containers(adapter.client, str(project_id), remove_volumes=True)
            # Best-effort: an internal=True network with no containers left on it is cheap and
            # harmless to leave behind, but cleaning it up keeps `docker network ls` honest.
            # Broad except deliberately (not just NotFound/DockerException): this must never
            # turn a successful stop+image-removal+teardown into a reported failure just
            # because the preview network step itself hiccupped.
            try:
                adapter.client.networks.get(_preview_network_name(str(project_id))).remove()
            except Exception:  # noqa: BLE001 - see comment above
                pass
            return {"ok": True}
        if action == "logs":
            container_id = extra.get("container_id")
            tail = int(extra.get("tail", 400) or 400)
            logs = DockerDeploymentAdapter().fetch_container_logs(str(container_id), tail=tail)
            return {"ok": True, "logs": logs}
        if action == "runtime_health_check" and project_id:
            return _run_runtime_health_check(str(project_id))
        if action == "build_check" and project_id:
            db = SessionLocal()
            try:
                project = db.get(Project, project_id)
                if not project:
                    return {"ok": False, "log": "Project not found"}
                return try_build_project_image(project)
            finally:
                db.close()
        if action == "preview" and project_id:
            db = SessionLocal()
            try:
                project = db.get(Project, project_id)
                if not project:
                    return {
                        "status": "failed",
                        "pages": [],
                        "fatal_errors": ["Project not found"],
                        "warnings": [],
                    }
                # Best-effort real-looking env (DB/cache connection strings, bot token if
                # already configured) so the previewed container renders like production
                # would. Never raises on a missing token - a container that can't boot
                # without it will simply surface as a failed page load, which is honest
                # signal on its own.
                environment = build_connection_env(db, project)
                if project.type in ("telegram_bot", "mixed"):
                    token = _telegram_token(db, project)
                    if token:
                        environment["TELEGRAM_BOT_TOKEN"] = token
                targets = extra.get("targets")
                paths = extra.get("paths")
                return run_preview(
                    project,
                    environment=environment,
                    targets=targets if isinstance(targets, list) else None,
                    paths=paths if isinstance(paths, list) else None,
                )
            finally:
                db.close()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - always report back
        logger.exception("Control action %r failed for project %s", action, project_id)
        return {"ok": False, "error": str(exc)}
