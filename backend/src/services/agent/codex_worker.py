"""Docker-side execution of a Codex run.

Only ever imported from the `worker` process - the one place in this platform allowed to touch
the Docker socket (see docker_control_queue.py). Runs a fresh, single-purpose Codex container per
turn (`docker run`, not `docker exec` into a shared always-on one) and yields its `codex exec
--json` output, one parsed event at a time, as it's produced.

Isolation model (replaces the old "one long-lived `codex` container, shared project volume,
raw host socket" setup - see git history for that version):
- Filesystem: each run's container gets ONLY the current project's own subtree bind-mounted (at
  /workspace), resolved from the shared named volume's real host path via _resolve_project_mount.
  A turn for project A can no longer `cd ../other-project` - that path doesn't exist in its mount
  namespace. If the volume's host path can't be resolved (older Docker, renamed volume, ...) this
  falls back to the old shared-mount behavior rather than breaking every turn outright - see
  _resolve_project_mount's docstring. That fallback is intentionally loud (printed, not silent).
- Docker access: if settings.codex_docker_host is configured (a docker-socket-proxy address),
  the container gets DOCKER_HOST pointed at the proxy instead of the raw host socket, so its own
  `docker build`/`docker run` calls (Codex still needs these - see prompt.py's bridge
  instructions) go through a narrowed API surface instead of the unscoped daemon. Unset by
  default so this ships non-breaking; see docker-compose.yml's docker-socket-proxy service and
  docs/architecture.md for the opt-in deploy step.

Two callers, matching the two ways docker_control_queue.py already lets worker-side Docker
actions run:
- execute_codex_run(): out-of-process case. The backend API process (which never touches
  Docker) queued a job; a background thread in deployment_worker.py calls this to relay events
  into Redis for agent/codex_runtime.py's async consumer.
- iter_codex_events(): in-process case, called directly by agent/codex_runtime.py when a repair
  flow is already running inside the worker (docker_control_queue.in_worker_inline_docker()) -
  going through Redis there would have the single worker process waiting on a queue only it
  services, which is the same self-deadlock worker_inline_docker() already exists to avoid for
  the plain stop/cleanup/logs/build_check actions.
"""

from __future__ import annotations

import json
import logging
import shlex
import uuid
from collections.abc import Iterator
from pathlib import PurePosixPath

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from redis import Redis

from src.core.config import settings
from src.services.system_settings import resolve_api_key_for_provider

logger = logging.getLogger(__name__)

_EVENTS_KEY_PREFIX = "codex:events:"
_DONE_MARKER = "__codex_run_done__"
_EVENTS_TTL_SECONDS = 600

_WORKSPACE_MOUNT = "/workspace"
# Sentinel exit code for "the login step itself failed" vs. any other container exit - chosen to
# not collide with common shell/exec codes (1, 2, 126, 127) so it's unambiguous in logs.
_LOGIN_FAILED_EXIT = 17


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _events_key(run_id: str) -> str:
    return f"{_EVENTS_KEY_PREFIX}{run_id}"


def _resolve_project_mount(client: docker.DockerClient, project_id: str) -> str | None:
    """Real host path of this project's own subtree inside the shared projects volume, so a
    fresh container can bind-mount just that one directory instead of the whole shared tree.

    Uses the volume's own `Mountpoint` (a long-standing, stable part of the Docker volume
    inspect API - not the newer, version-gated volume-subpath mount feature, which would need
    Docker Engine 25+ and wasn't safe to assume here) rather than switching the shared volume
    itself to a host bind-mount, which would've meant a manual data-migration step for anyone
    upgrading. Returns None (triggering the shared-mount fallback in the caller) if the volume
    name doesn't match what's actually on this host - e.g. a non-default COMPOSE_PROJECT_NAME -
    rather than raising, since a degraded-but-working turn beats a hard-broken one.
    """
    try:
        volume = client.volumes.get(settings.generated_projects_volume_name)
        mountpoint = volume.attrs.get("Mountpoint")
        if not mountpoint:
            return None
        # PurePosixPath, not Path: this always runs against a Linux Docker daemon (the worker
        # container, or a Linux/Docker Desktop dev host) regardless of what OS the interpreter
        # itself happens to be on - using the platform Path here silently produced backslash
        # paths (and a broken bind-mount source) when this was exercised on Windows.
        return str(PurePosixPath(mountpoint) / project_id)
    except (NotFound, APIError, DockerException, KeyError) as exc:
        logger.warning(
            "Could not resolve per-project mount for volume %r (%s) - falling back to full "
            "shared-volume access for this run. Check GENERATED_PROJECTS_VOLUME_NAME / "
            "`docker volume ls` on this host.",
            settings.generated_projects_volume_name,
            exc,
        )
        return None


def _build_argv(job: dict, *, model: str, remapped_cwd: str | None) -> list[str]:
    # NOTE: flag names (--skip-git-repo-check, --dangerously-bypass-approvals-and-sandbox,
    # --cd, --image) match the Codex CLI docs at the time this was written. `exec` has no TTY
    # to prompt for approval, so it must run with its own sandbox/approval gate fully open - the
    # per-run Docker container (this project's own subtree + Docker access only, never the host
    # filesystem) is the sandbox here, not Codex's internal one. Re-check `codex exec --help` in
    # the built image after a CLI upgrade if runs start failing to parse args.
    argv = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
    ]
    if remapped_cwd:
        argv += ["--cd", remapped_cwd]
    for image_path in job.get("image_paths") or []:
        argv += ["--image", str(image_path)]
    argv.append(str(job.get("prompt") or ""))
    return argv


def _remap_under_workspace(path_str: str, old_root: str) -> str:
    """--image paths arrive as absolute paths under the old shared-tree root (see
    file_context.py / codex_runtime.py's _write_temp_images, which writes under the project's own
    directory) - rewrite them to sit under this run's /workspace mount instead."""
    try:
        relative = PurePosixPath(path_str).relative_to(old_root)
    except ValueError:
        return path_str
    return str(PurePosixPath(_WORKSPACE_MOUNT) / relative)


def _login_and_exec_command(argv: list[str]) -> list[str]:
    """`codex exec` does not read OPENAI_API_KEY itself - confirmed against a real run, which
    401'd until this was added. Auth is a separate step that persists to ~/.codex/auth.json
    inside the container (`codex login --with-api-key`, fed the key over stdin); once logged in,
    `codex exec` picks it up with no per-call key needed. Chained into one shell command (rather
    than a separate exec_create call, as the old shared-container version did) because this run's
    container no longer stays alive independently for a follow-up exec - login-then-run is now
    the container's one and only job. Re-logs in on every run (cheap, local, no network
    round-trip) rather than trying to persist/cache auth across runs - simplest way to stay
    correct if the admin rotates the key."""
    login = 'printf "%s" "$OPENAI_API_KEY" | codex login --with-api-key'
    exec_cmd = shlex.join(argv)
    script = (
        f"if ! {login} >/tmp/codex-login.log 2>&1; then "
        f"cat /tmp/codex-login.log >&2; exit {_LOGIN_FAILED_EXIT}; "
        f"fi; exec {exec_cmd}"
    )
    return ["sh", "-c", script]


def _container_env(api_key: str) -> dict[str, str]:
    env = {"OPENAI_API_KEY": api_key}
    if settings.codex_docker_host:
        env["DOCKER_HOST"] = settings.codex_docker_host
    return env


def _container_volumes(project_host_path: str | None) -> dict[str, dict[str, str]]:
    volumes: dict[str, dict[str, str]] = {}
    if project_host_path:
        volumes[project_host_path] = {"bind": _WORKSPACE_MOUNT, "mode": "rw"}
    if not settings.codex_docker_host:
        # No proxy configured - fall back to the raw host socket (the pre-isolation trust level)
        # so Codex can still build/run project images. Deliberately opt-in-to-narrow rather than
        # opt-in-to-broad: safer default is "at least as isolated as before", not "silently open".
        volumes["/var/run/docker.sock"] = {"bind": "/var/run/docker.sock", "mode": "rw"}
    return volumes


def iter_codex_events(job: dict) -> Iterator[dict]:
    """Blocking generator: runs a fresh per-turn Codex container and yields each parsed JSON
    event as it's produced. Safe to call directly in-process (see module docstring) - it never
    touches Redis itself, so it has no opinion on whether its caller is the worker's main loop or
    an inline repair flow."""
    container = None
    client: docker.DockerClient | None = None
    try:
        api_key = resolve_api_key_for_provider("openai") or settings.openai_api_key
        if not api_key:
            yield {"type": "infra_error", "message": "OpenAI API key is not configured"}
            return

        client = docker.from_env()
        try:
            client.images.get(settings.codex_image)
        except ImageNotFound:
            yield {
                "type": "infra_error",
                "message": (
                    f"Codex image {settings.codex_image!r} is not built - run "
                    "`docker compose build codex`"
                ),
            }
            return

        # cwd follows agent/codex_runtime.py's own `f"{generated_projects_dir}/{project_id}"`
        # construction (both _run_inline and _run_via_queue build it that way) - the project id
        # is just its last path segment, recovered here rather than widening the job dict, since
        # both call sites already agree on this exact shape.
        old_cwd = job.get("cwd")
        project_id = PurePosixPath(old_cwd).name if old_cwd else None
        project_host_path = _resolve_project_mount(client, project_id) if project_id else None

        volumes = _container_volumes(project_host_path)
        if old_cwd and project_host_path:
            # Scoped mount resolved - remap --cd and any --image paths onto it.
            effective_cwd = _WORKSPACE_MOUNT
            effective_images = [
                _remap_under_workspace(p, old_cwd) for p in (job.get("image_paths") or [])
            ]
        elif old_cwd:
            # Could not resolve a scoped mount (see _resolve_project_mount) - fall back to the
            # whole shared tree at its original absolute path, exactly as before isolation
            # existed, so this turn still succeeds instead of hard-failing.
            effective_cwd = old_cwd
            effective_images = list(job.get("image_paths") or [])
            volumes[settings.generated_projects_dir] = {
                "bind": settings.generated_projects_dir,
                "mode": "rw",
            }
        else:
            # codex_simple_complete: no project context, nothing to mount.
            effective_cwd = None
            effective_images = []

        model = job.get("model") or settings.default_model_openai
        argv = _build_argv(
            {**job, "image_paths": effective_images}, model=model, remapped_cwd=effective_cwd
        )
        command = _login_and_exec_command(argv)

        try:
            container = client.containers.run(
                settings.codex_image,
                command=command,
                detach=True,
                name=f"airuntime-codex-{uuid.uuid4().hex[:12]}",
                environment=_container_env(api_key),
                volumes=volumes,
                network=settings.codex_network,
                mem_limit=settings.codex_memory_limit,
                nano_cpus=int(float(settings.codex_cpu_limit) * 1_000_000_000),
                working_dir=effective_cwd,
            )
        except DockerException as exc:
            yield {"type": "infra_error", "message": f"Could not start Codex container: {exc}"}
            return

        buffer = b""
        for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=False):
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                yield payload

        tail = buffer.decode("utf-8", errors="replace").strip()
        if tail:
            try:
                yield json.loads(tail)
            except json.JSONDecodeError:
                pass

        result = container.wait()
        exit_code = result.get("StatusCode")
        if exit_code == _LOGIN_FAILED_EXIT:
            detail = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            yield {"type": "infra_error", "message": f"Codex login failed: {detail.strip()[:500]}"}
        elif exit_code not in (0, None):
            yield {"type": "infra_error", "message": f"codex exec exited with code {exit_code}"}
    except (DockerException, APIError) as exc:
        logger.warning("Codex run: Docker error: %s", exc)
        yield {"type": "infra_error", "message": f"Docker error: {exc}"}
    except Exception as exc:  # noqa: BLE001 - report rather than crash the caller
        logger.exception("Codex run failed unexpectedly")
        yield {"type": "infra_error", "message": f"Codex run failed: {exc}"}
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except DockerException:
                pass


def execute_codex_run(job: dict) -> None:
    """Out-of-process entry point: relay iter_codex_events() into Redis so
    agent/codex_runtime.py's async stream_codex_events() can consume it live. Used when the
    backend API process (no Docker access) initiated the turn - see
    deployment_worker.py's _spawn_codex_run."""
    run_id = job["job_id"]
    r = _redis()
    key = _events_key(run_id)
    try:
        for payload in iter_codex_events(job):
            r.rpush(key, json.dumps(payload))
            r.expire(key, _EVENTS_TTL_SECONDS)
    finally:
        try:
            r.rpush(key, _DONE_MARKER)
            r.expire(key, _EVENTS_TTL_SECONDS)
        except Exception:  # noqa: BLE001 - nothing more we can do if Redis itself is down
            pass
