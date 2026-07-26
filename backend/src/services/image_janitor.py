"""Periodic sweep for explicitly project-scoped scratch images created by Codex self-tests.

Three independent checks, all required, so this can run unattended on a schedule without risking
a platform-managed or currently-needed image:
- Age gate: never touch anything created within the last _MIN_AGE_SECONDS, so this can't race a
  build that's still in progress.
- Positive ownership allowlist: only touch `airuntime-scratch-*`. Unknown host images are never
  AIRuntime's property; treating "not airuntime-*" as disposable previously deleted unrelated
  local images on worker startup.
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
_SCRATCH_PREFIX = "airuntime-scratch-"


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
    """Remove old, unreferenced AIRuntime scratch images. Returns removed tag(s)."""
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
        if not any(tag.startswith(_SCRATCH_PREFIX) for tag in tags):
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
