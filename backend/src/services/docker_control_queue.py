"""Synchronous-feeling RPC over Redis so the (internet-facing, agent-code-adjacent) backend
process never needs direct Docker socket access - only the worker container has that. The
backend pushes a job and blocks on a per-job result key; the worker pops the job, does the
real docker.from_env() call, and pushes the result back.
"""

from __future__ import annotations

import json
import uuid

from redis import Redis
from redis.exceptions import RedisError

from src.core.config import settings

QUEUE_KEY = "docker_control:jobs"
RESULT_PREFIX = "docker_control:result:"


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def submit_control_job(
    *, action: str, project_id: str, timeout_seconds: int = 20, extra: dict | None = None
) -> dict | None:
    """Push a control job and block for the worker's result. Returns None if Redis/the worker
    is unreachable or the job timed out - callers should treat that as "couldn't confirm",
    not as a hard failure, since Docker itself may just be briefly unavailable."""
    job_id = uuid.uuid4().hex
    job = {"job_id": job_id, "action": action, "project_id": project_id, **(extra or {})}
    result_key = f"{RESULT_PREFIX}{job_id}"
    try:
        r = _redis()
        r.rpush(QUEUE_KEY, json.dumps(job))
        popped = r.blpop(result_key, timeout=timeout_seconds)
    except RedisError:
        return None
    if not popped:
        return None
    _, payload = popped
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def pop_control_job(timeout_seconds: int = 2) -> dict | None:
    try:
        result = _redis().blpop(QUEUE_KEY, timeout=timeout_seconds)
    except RedisError:
        return None
    if not result:
        return None
    _, payload = result
    return json.loads(payload)


def push_control_result(job_id: str, result: dict) -> None:
    result_key = f"{RESULT_PREFIX}{job_id}"
    try:
        r = _redis()
        r.rpush(result_key, json.dumps(result))
        r.expire(result_key, 60)
    except RedisError:
        pass
