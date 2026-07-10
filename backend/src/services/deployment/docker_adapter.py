import re
from dataclasses import dataclass

import docker
from docker.errors import DockerException, NotFound

from src.core.config import settings


@dataclass
class DeployRequest:
    project_id: str
    image_ref: str
    subdomain: str
    environment: dict[str, str] | None = None
    expose_http: bool = True


class DockerDeploymentAdapter:
    """Deploy per-project containers via the Docker Engine API."""

    def __init__(self) -> None:
        self._client = docker.from_env()

    def fetch_container_logs(self, container_id: str, *, tail: int = 400) -> str:
        try:
            container = self._client.containers.get(container_id)
            raw_logs = container.logs(tail=tail, timestamps=True)
        except NotFound as exc:
            raise RuntimeError(f"Container {container_id} was not found.") from exc
        return raw_logs.decode("utf-8", errors="replace")

    def stop_project(self, project_id: str) -> None:
        container_name = f"airuntime-{project_id[:8]}"
        for existing in self._client.containers.list(all=True, filters={"name": container_name}):
            try:
                if existing.status == "running":
                    existing.stop(timeout=10)
            except DockerException:
                pass
            try:
                existing.remove(force=True)
            except DockerException:
                pass

    def deploy(self, request: DeployRequest) -> dict:
        container_name = f"airuntime-{request.project_id[:8]}"
        host_port = self._allocate_port(request.project_id)
        deploy_url = settings.build_project_url(request.subdomain)
        service_name = re.sub(r"[^a-z0-9-]", "-", container_name.lower()).strip("-")

        for existing in self._client.containers.list(all=True, filters={"name": container_name}):
            existing.remove(force=True)

        try:
            ports = (
                {"80/tcp": host_port}
                if request.expose_http and settings.deployment_expose_host_ports
                else None
            )
            labels = {
                "airuntime.project_id": request.project_id,
                "airuntime.managed": "true",
            }
            if request.expose_http and settings.deployment_public_network:
                host = f"{request.subdomain}.{settings.resolved_app_domain}"
                labels.update(
                    {
                        "traefik.enable": "true",
                        "traefik.docker.network": settings.deployment_public_network,
                        f"traefik.http.routers.{service_name}.rule": f"Host(`{host}`)",
                        f"traefik.http.routers.{service_name}.entrypoints": "websecure",
                        f"traefik.http.routers.{service_name}.tls.certresolver": "letsencrypt",
                        f"traefik.http.routers.{service_name}.service": service_name,
                        f"traefik.http.services.{service_name}.loadbalancer.server.port": "80",
                    }
                )
            container = self._client.containers.run(
                request.image_ref,
                detach=True,
                name=container_name,
                labels=labels,
                ports=ports,
                environment=request.environment or None,
                mem_limit=settings.deployment_memory_limit,
                nano_cpus=int(float(settings.deployment_cpu_limit) * 1_000_000_000),
                network=settings.deployment_public_network
                if request.expose_http and settings.deployment_public_network
                else None,
            )
        except DockerException as exc:
            raise RuntimeError(str(exc)) from exc

        container.reload()
        if container.status != "running":
            raise RuntimeError(f"Container is not running (status: {container.status})")

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
