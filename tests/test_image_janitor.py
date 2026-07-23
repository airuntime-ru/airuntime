import time
from datetime import UTC, datetime, timedelta

from src.services import image_janitor


class _FakeImage:
    def __init__(self, image_id: str, tags: list[str], created) -> None:
        self.id = image_id
        self.tags = tags
        self.attrs = {"Created": created}


class _FakeImageRef:
    def __init__(self, image_id: str) -> None:
        self.id = image_id


class _FakeContainer:
    def __init__(self, image_id: str) -> None:
        self.image = _FakeImageRef(image_id)


class _FakeImages:
    def __init__(self, images: list[_FakeImage]) -> None:
        self._images = images
        self.removed: list[str] = []

    def list(self) -> list[_FakeImage]:
        return list(self._images)

    def remove(self, image: str, force: bool = False) -> None:
        self.removed.append(image)


class _FakeContainers:
    def __init__(self, containers: list[_FakeContainer]) -> None:
        self._containers = containers

    def list(self, all: bool = False) -> list[_FakeContainer]:
        return list(self._containers)


class _FakeClient:
    def __init__(self, images: list[_FakeImage], containers: list[_FakeContainer]) -> None:
        self.images = _FakeImages(images)
        self.containers = _FakeContainers(containers)


def _iso(hours_ago: float, *, nanos: bool = False) -> str:
    dt = datetime.now(UTC) - timedelta(hours=hours_ago)
    base = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if nanos:
        # Docker's real precision (9 fractional digits) - exercises the truncate-to-6 path.
        return f"{base}.{dt.microsecond:06d}789Z"
    return f"{base}Z"


def test_sweep_removes_only_old_unreferenced_non_platform_images():
    """Mirrors the real leftovers found 2026-07-23 (beer-site, alpha-romeo-service, ...): only
    the genuinely-orphaned ad-hoc test image gets removed - dangling, platform-prefixed,
    still-referenced, and too-recent images are all left alone."""
    images = [
        _FakeImage("img-dangling", [], _iso(10)),
        _FakeImage("img-platform", ["airuntime-generated-site-abc123456789:latest"], _iso(10)),
        _FakeImage("img-referenced", ["postgres:16-alpine"], _iso(10)),
        _FakeImage("img-fresh", ["fresh-test:latest"], _iso(0.1)),
        _FakeImage("img-orphan", ["beer-site:latest"], _iso(10)),
        _FakeImage("img-orphan-ns", ["alpha-romeo-service:latest"], _iso(10, nanos=True)),
    ]
    containers = [_FakeContainer("img-referenced")]
    client = _FakeClient(images, containers)

    removed = image_janitor.sweep_unrecognized_images(client)

    assert set(removed) == {"beer-site:latest", "alpha-romeo-service:latest"}
    assert set(client.images.removed) == {"img-orphan", "img-orphan-ns"}


def test_sweep_handles_epoch_created_and_leaves_unparseable_created_alone():
    old_epoch = time.time() - 10 * 3600
    images = [
        _FakeImage("img-epoch-old", ["scratch-epoch:latest"], old_epoch),
        _FakeImage("img-bad-created", ["scratch-bad:latest"], "not-a-date"),
    ]
    client = _FakeClient(images, [])

    removed = image_janitor.sweep_unrecognized_images(client)

    assert removed == ["scratch-epoch:latest"]


def test_sweep_never_touches_a_running_container_error_path():
    """images.remove() raising (e.g. a container started using it between listing and removal)
    must not blow up the sweep or count as removed."""

    class _RaisingImages(_FakeImages):
        def remove(self, image: str, force: bool = False) -> None:
            raise RuntimeError("image is being used by a running container")

    client = _FakeClient([_FakeImage("img-orphan", ["beer-site:latest"], _iso(10))], [])
    client.images = _RaisingImages(client.images._images)

    removed = image_janitor.sweep_unrecognized_images(client)

    assert removed == []
