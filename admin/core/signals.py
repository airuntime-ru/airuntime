import logging

import docker
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from docker.errors import DockerException

from core.models import Project

logger = logging.getLogger(__name__)


def _stop_and_remove_containers(project_id: str) -> None:
    try:
        client = docker.from_env()
    except DockerException:
        logger.warning("Docker unavailable, skipping container cleanup for project %s", project_id)
        return
    try:
        containers = client.containers.list(
            all=True, filters={"label": f"airuntime.project_id={project_id}"}
        )
    except DockerException as exc:
        logger.warning("Could not list containers for project %s: %s", project_id, exc)
        return
    for container in containers:
        try:
            if container.status == "running":
                container.stop(timeout=10)
            container.remove(force=True)
        except DockerException as exc:
            logger.warning(
                "Could not stop/remove container %s for project %s: %s",
                container.name,
                project_id,
                exc,
            )


@receiver(pre_delete)
def cleanup_project_container(sender, instance, **kwargs) -> None:
    # No `sender=Project` filter: the admin UI deletes through the DomainProject proxy model
    # (domain/admin.py), and Django signals for proxy models fire with the proxy as sender, not
    # the base class - isinstance() catches Project and any of its proxies uniformly.
    if isinstance(instance, Project):
        _stop_and_remove_containers(str(instance.id))
