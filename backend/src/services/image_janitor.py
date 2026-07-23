"""Periodic sweep for locally-built Docker images that Codex creates on its own while
self-testing a turn (e.g. `docker build -t some-name .` to smoke-test a build, `docker run
--rm ...` to try it - see agent/codex_runtime.py's bridge instructions, which grant it plain
shell/Docker access). These are deliberately outside the platform's own build_project_image
pipeline, so there's no naming convention to clean them up by, unlike the per-project
`airuntime-generated-*` images (see docker_adapter.py's remove_project_images). Confirmed live
2026-07-23: a single test session left `alfa-romeo-service`, `alpha-romeo-service`,
`alfa-cabinet`, `beer-site` etc. sitting in `docker images` with nothing ever removing them.

Three independent checks, all required, so this can run unattended on a schedule without risking
a platform-managed or currently-needed image:
- Age gate: never touch anything created within the last _MIN_AGE_SECONDS, so this can't race a
  build that's still in progress.
- Prefix allowlist: never touch anything tagged "airuntime-*" - covers every image this platform
  builds itself (per-project deploys, backend/worker/frontend/codex/django-admin all share this
  prefix per Compose's default `<project>-<service>` build naming).
- Reference check: never touch an image that any container (running OR stopped) still points at -
  covers every pulled base image (postgres, redis, traefik, minio, the request_service presets,
  ...), since Compose's `restart: unless-stopped` containers for those keep existing as container
  objects across restarts, not just while running.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_MIN_AGE_SECONDS = 2 * 3600
_PROTECTED_PREFIX = "airuntime-"


def _parse_docker_created(value: Any) -> float | None:
    """Docker's image `Created` is an ISO8601 string with up to 9 fractional digits from
    inspect/images.list(), but defensively also accept a bare unix-epoch number. Never raises -
    a failure to parse means "assume not old enough", the safe direction for this sweep."""
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value
    if text.endswith("Z"):
        body, _, frac = text[:-1].partition(".")
        text = f"{body}.{frac[:6]}+00:00" if frac else f"{body}+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def sweep_unrecognized_images(client: Any) -> list[str]:
    """Remove old, unreferenced, non-platform images. Returns the tag(s) of everything removed."""
    removed: list[str] = []
    try:
        images = client.images.list()
        containers = client.containers.list(all=True)
    except Exception:  # noqa: BLE001 - a listing failure just means "nothing to do this round"
        return removed

    referenced_image_ids: set[str] = set()
    for container in containers:
        try:
            referenced_image_ids.add(container.image.id)
        except Exception:  # noqa: BLE001 - a container in a weird state shouldn't abort the sweep
            continue

    cutoff = time.time() - _MIN_AGE_SECONDS
    for image in images:
        tags = getattr(image, "tags", None) or []
        if not tags:
            continue  # dangling - deploy.sh's `docker image prune` already handles these
        if any(tag.startswith(_PROTECTED_PREFIX) for tag in tags):
            continue
        if image.id in referenced_image_ids:
            continue
        created = _parse_docker_created((getattr(image, "attrs", None) or {}).get("Created"))
        if created is None or created > cutoff:
            continue
        try:
            client.images.remove(image=image.id, force=True)
        except Exception:  # noqa: BLE001 - best-effort; next sweep tries again
            continue
        removed.extend(tags)

    if removed:
        logger.info("Image janitor removed %d ad-hoc image(s): %s", len(removed), removed)
    return removed
