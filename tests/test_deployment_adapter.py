from docker.errors import NotFound

from src.core.config import settings
from src.services.deployment import docker_adapter
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter


class _FakeContainer:
    id = "container-123"
    status = "running"

    def reload(self) -> None:
        pass


class _FakeContainers:
    def __init__(self) -> None:
        self.run_kwargs = None

    def list(self, all: bool, filters: dict[str, str]) -> list:
        return []

    def run(self, *args, **kwargs) -> _FakeContainer:
        self.run_kwargs = kwargs
        return _FakeContainer()


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


def test_deploy_attaches_second_network_when_service_network_given(monkeypatch):
    client = _FakeDockerClient()
    monkeypatch.setattr(docker_adapter.docker, "from_env", lambda: client)
    monkeypatch.setattr(settings, "deployment_public_network", "airuntime_public")
    monkeypatch.setattr(settings, "deployment_expose_host_ports", False)

    adapter = DockerDeploymentAdapter()
    network_name = adapter.ensure_private_network("33333333-3333-4333-8333-333333333333")

    adapter.deploy(
        DeployRequest(
            project_id="33333333-3333-4333-8333-333333333333",
            image_ref="airuntime-generated-site:latest",
            subdomain="demo-33333333",
            service_network=network_name,
        )
    )

    assert client.networks.get(network_name).connected_containers == ["container-123"]
