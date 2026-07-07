from dataclasses import dataclass
import re

import docker
from docker.errors import DockerException

from src.core.config import settings


@dataclass
class DeployRequest:
    project_id: str
    image_ref: str
    subdomain: str


class DockerDeploymentAdapter:
    """Deploy per-project containers via the Docker Engine API."""

    def __init__(self) -> None:
        self._client = docker.from_env()

    def deploy(self, request: DeployRequest) -> dict:
        container_name = f"airuntime-{request.project_id[:8]}"
        host_port = self._allocate_port(request.project_id)
        deploy_url = settings.build_project_url(request.subdomain)

        for existing in self._client.containers.list(all=True, filters={"name": container_name}):
            existing.remove(force=True)

        try:
            container = self._client.containers.run(
                request.image_ref,
                detach=True,
                name=container_name,
                labels={
                    "airuntime.project_id": request.project_id,
                    "airuntime.managed": "true",
                },
                ports={"80/tcp": host_port},
                mem_limit=settings.deployment_memory_limit,
                nano_cpus=int(float(settings.deployment_cpu_limit) * 1_000_000_000),
            )
        except DockerException as exc:
            raise RuntimeError(str(exc)) from exc

        container_id = container.id
        logs_ref = f"docker://{container_id}"

        return {
            "status": "running",
            "container_id": container_id,
            "url": deploy_url,
            "host_port": host_port,
            "image_ref": request.image_ref,
            "logs_ref": logs_ref,
        }

    def _allocate_port(self, project_id: str) -> int:
        base = settings.deployment_port_base
        offset = int(project_id.replace("-", "")[:6], 16) % 5000
        return base + offset


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return slug or "project"
