from docker.errors import NotFound

from src.core.config import settings
from src.services.deployment import docker_adapter
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter


class _FakeContainer:
    id = "container-123"
    status = "running"
    name = "airuntime-11111111"
    labels: dict[str, str] = {}

    def __init__(self, name: str = "airuntime-11111111", labels: dict[str, str] | None = None):
        self.name = name
        self.labels = labels or {}
        self.removed = False

    def reload(self) -> None:
        pass

    def remove(self, force: bool = False) -> None:
        self.removed = True

    def stop(self, timeout: int = 10) -> None:
        self.status = "exited"


class _FakeContainers:
    def __init__(self) -> None:
        self.run_kwargs = None
        self._listed: list[_FakeContainer] = []

    def list(self, all: bool, filters: dict[str, str]) -> list:
        needle = (filters or {}).get("name", "")
        return [c for c in self._listed if needle in (c.name or "")]

    def run(self, *args, **kwargs) -> _FakeContainer:
        self.run_kwargs = kwargs
        return _FakeContainer(name=kwargs.get("name", "airuntime-11111111"))


class _FakeNetwork:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected_containers: list[str] = []

    def connect(self, container_id: str) -> None:
        self.connected_containers.append(container_id)

    def remove(self) -> None:
        pass


class _FakeNetworks:
    def __init__(self) -> None:
        self._networks: dict[str, _FakeNetwork] = {}

    def get(self, name: str) -> _FakeNetwork:
        if name not in self._networks:
            raise NotFound("network not found")
        return self._networks[name]

    def create(self, name: str, driver: str = "bridge") -> _FakeNetwork:
        network = _FakeNetwork(name)
        self._networks[name] = network
        return network


class _FakeDockerClient:
    def __init__(self) -> None:
        self.containers = _FakeContainers()
        self.networks = _FakeNetworks()


def test_deploy_uses_traefik_labels_without_host_ports(monkeypatch):
    client = _FakeDockerClient()
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)
    monkeypatch.setattr(settings, "deployment_public_network", "airuntime_public")
    monkeypatch.setattr(settings, "deployment_expose_host_ports", False)
    monkeypatch.setattr(settings, "app_domain", "airuntime.ru")
    monkeypatch.setattr(settings, "public_base_domain", None)

    result = DockerDeploymentAdapter().deploy(
        DeployRequest(
            project_id="11111111-1111-4111-8111-111111111111",
            image_ref="airuntime-generated-site:latest",
            subdomain="demo-11111111",
        )
    )

    labels = client.containers.run_kwargs["labels"]
    assert result["url"] == "https://demo-11111111.airuntime.ru"
    assert client.containers.run_kwargs["ports"] is None
    assert client.containers.run_kwargs["network"] == "airuntime_public"
    assert client.containers.run_kwargs["restart_policy"] == {"Name": "unless-stopped"}
    assert labels["traefik.enable"] == "true"
    assert labels["traefik.http.routers.airuntime-11111111.rule"] == (
        "Host(`demo-11111111.airuntime.ru`)"
    )


def test_deploy_maps_host_port_without_public_network(monkeypatch):
    client = _FakeDockerClient()
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)
    monkeypatch.setattr(settings, "deployment_public_network", None)
    monkeypatch.setattr(settings, "deployment_expose_host_ports", True)

    DockerDeploymentAdapter().deploy(
        DeployRequest(
            project_id="22222222-2222-4222-8222-222222222222",
            image_ref="airuntime-generated-site:latest",
            subdomain="demo-22222222",
        )
    )

    assert client.containers.run_kwargs["ports"] == {"80/tcp": 19962}
    assert client.containers.run_kwargs["network"] is None
    assert "traefik.enable" not in client.containers.run_kwargs["labels"]


def test_deploy_attaches_public_network_when_service_network_given(monkeypatch):
    """App starts on the private service network, then attaches Traefik/public second."""
    client = _FakeDockerClient()
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)
    monkeypatch.setattr(settings, "deployment_public_network", "airuntime_public")
    monkeypatch.setattr(settings, "deployment_expose_host_ports", False)

    adapter = DockerDeploymentAdapter()
    client.networks.create("airuntime_public")
    network_name = adapter.ensure_private_network("33333333-3333-4333-8333-333333333333")

    adapter.deploy(
        DeployRequest(
            project_id="33333333-3333-4333-8333-333333333333",
            image_ref="airuntime-generated-site:latest",
            subdomain="demo-33333333",
            service_network=network_name,
        )
    )

    assert client.containers.run_kwargs["network"] == network_name
    assert client.networks.get("airuntime_public").connected_containers == ["container-123"]


def test_deploy_cleanup_does_not_remove_postgres_sidecar(monkeypatch):
    client = _FakeDockerClient()
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)
    monkeypatch.setattr(settings, "deployment_public_network", "airuntime_public")
    monkeypatch.setattr(settings, "deployment_expose_host_ports", False)

    project_id = "44444444-4444-4444-8444-444444444444"
    app = _FakeContainer(name="airuntime-44444444")
    postgres = _FakeContainer(
        name="airuntime-44444444-postgres",
        labels={"airuntime.role": "service", "airuntime.project_id": project_id},
    )
    client.containers._listed = [app, postgres]

    DockerDeploymentAdapter().deploy(
        DeployRequest(
            project_id=project_id,
            image_ref="airuntime-generated-bot:latest",
            subdomain="demo-44444444",
            expose_http=False,
            service_network="airuntime-svc-44444444",
        )
    )

    assert app.removed is True
    assert postgres.removed is False
