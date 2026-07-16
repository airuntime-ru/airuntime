"""Docker-side execution of a Codex run.

Only ever imported from the `worker` process - the one place in this platform allowed to touch
the Docker socket (see docker_control_queue.py). `docker exec`s into the always-on `codex`
container (deployment/codex/Dockerfile) and yields its `codex exec --json` output, one parsed
event at a time, as it's produced.

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
from collections.abc import Iterator

import docker
from docker.errors import APIError, DockerException, NotFound
from redis import Redis

from src.core.config import settings
from src.services.system_settings import resolve_api_key_for_provider

_EVENTS_KEY_PREFIX = "codex:events:"
_DONE_MARKER = "__codex_run_done__"
_EVENTS_TTL_SECONDS = 600


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _events_key(run_id: str) -> str:
    return f"{_EVENTS_KEY_PREFIX}{run_id}"


def _build_argv(job: dict, *, model: str) -> list[str]:
    # NOTE: flag names (--skip-git-repo-check, --dangerously-bypass-approvals-and-sandbox,
    # --cd, --image) match the Codex CLI docs at the time this was written. `exec` has no TTY
    # to prompt for approval, so it must run with its own sandbox/approval gate fully open - the
    # Docker container (project-volume + socket only, no host filesystem) is the sandbox here,
    # not Codex's internal one. Re-check `codex exec --help` in the built image after a CLI
    # upgrade if runs start failing to parse args.
    argv = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
    ]
    cwd = job.get("cwd")
    if cwd:
        argv += ["--cd", str(cwd)]
    for image_path in job.get("image_paths") or []:
        argv += ["--image", str(image_path)]
    argv.append(str(job.get("prompt") or ""))
    return argv


def _login(client: docker.DockerClient, container, api_key: str) -> str | None:
    """`codex exec` does not read OPENAI_API_KEY itself - confirmed against a real run, which
    401'd until this was added. Auth is a separate step that persists to ~/.codex/auth.json
    inside the container (`codex login --with-api-key`, fed the key over stdin); once logged in,
    `codex exec` picks it up with no per-call key needed. Piping through a shell here avoids
    dealing with docker-py's raw stdin socket for what the CLI itself treats as an interactive
    stdin read. Re-run before every exec (cheap, local, no network round-trip) rather than
    trying to cache "already logged in" - simplest way to stay correct if the admin rotates the
    key, and worst case two concurrent turns briefly race to (re)write the same file with
    whatever the currently-configured key is.
    """
    exec_id = client.api.exec_create(
        container.id,
        ["sh", "-c", 'printf "%s" "$OPENAI_API_KEY" | codex login --with-api-key'],
        environment={"OPENAI_API_KEY": api_key},
        stdout=True,
        stderr=True,
    )["Id"]
    output = client.api.exec_start(exec_id)
    if client.api.exec_inspect(exec_id).get("ExitCode") != 0:
        return f"Codex login failed: {output.decode('utf-8', errors='replace').strip()[:500]}"
    return None


def iter_codex_events(job: dict) -> Iterator[dict]:
    """Blocking generator: execs into the codex container and yields each parsed JSON event as
    it's produced. Safe to call directly in-process (see module docstring) - it never touches
    Redis itself, so it has no opinion on whether its caller is the worker's main loop or an
    inline repair flow."""
    try:
        api_key = resolve_api_key_for_provider("openai") or settings.openai_api_key
        if not api_key:
            yield {"type": "infra_error", "message": "OpenAI API key is not configured"}
            return

        client = docker.from_env()
        try:
            container = client.containers.get(settings.codex_container_name)
        except NotFound:
            yield {"type": "infra_error", "message": "Codex runner container is not running"}
            return

        login_error = _login(client, container, api_key)
        if login_error:
            yield {"type": "infra_error", "message": login_error}
            return

        model = job.get("model") or settings.default_model_openai
        argv = _build_argv(job, model=model)

        exec_id = client.api.exec_create(
            container.id,
            argv,
            stdout=True,
            stderr=True,
        )["Id"]
        # demux=True keeps stdout/stderr separate without manually stripping Docker's exec
        # stream-multiplexing frame headers - we only care about stdout (the --json NDJSON).
        stream = client.api.exec_start(exec_id, stream=True, demux=True)

        buffer = b""
        for stdout_chunk, _stderr_chunk in stream:
            if not stdout_chunk:
                continue
            buffer += stdout_chunk
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

        exit_code = client.api.exec_inspect(exec_id).get("ExitCode")
        if exit_code not in (0, None):
            yield {"type": "infra_error", "message": f"codex exec exited with code {exit_code}"}
    except (DockerException, APIError) as exc:
        yield {"type": "infra_error", "message": f"Docker error: {exc}"}
    except Exception as exc:  # noqa: BLE001 - report rather than crash the caller
        yield {"type": "infra_error", "message": f"Codex run failed: {exc}"}


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
