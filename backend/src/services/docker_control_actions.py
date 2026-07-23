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
from src.services.artifacts import try_build_project_image
from src.services.deployment.docker_adapter import DockerDeploymentAdapter
from src.services.project_services import teardown_service_containers

logger = logging.getLogger(__name__)


def run_control_action(
    *, action: str | None, project_id: str | None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run one control action and return a result dict (ok=True/False, …)."""
    extra = extra or {}
    try:
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
            return {"ok": True}
        if action == "logs":
            container_id = extra.get("container_id")
            tail = int(extra.get("tail", 400) or 400)
            logs = DockerDeploymentAdapter().fetch_container_logs(str(container_id), tail=tail)
            return {"ok": True, "logs": logs}
        if action == "build_check" and project_id:
            db = SessionLocal()
            try:
                project = db.get(Project, project_id)
                if not project:
                    return {"ok": False, "log": "Project not found"}
                return try_build_project_image(project)
            finally:
                db.close()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - always report back
        logger.exception("Control action %r failed for project %s", action, project_id)
        return {"ok": False, "error": str(exc)}
