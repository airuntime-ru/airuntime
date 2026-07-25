"""A real, minimal MCP (Model Context Protocol) client: JSON-RPC 2.0 over stdio (spawned
subprocess) or HTTP, implementing the core subset a capability-invoking platform needs -
`initialize`, `tools/list`, `tools/call`. Does not implement the rest of the MCP spec
(resources/prompts/sampling/roots) - an honest scope limitation, not an oversight; nothing in
this platform needs those yet, and adding them later is additive, not a breaking change to this
module's shape.

Security properties, per spec section 11:
  - timeout on every call (`timeout_seconds`), so a hung server can't hang a task forever.
  - per-server circuit breaker: after repeated consecutive failures, calls fail fast instead of
    retrying into a known-bad server.
  - bounded retries with backoff on transient failures.
  - result size cap (`MAX_RESULT_BYTES`) - an oversized tool result is truncated, never passed
    through wholesale (defends against a misbehaving/malicious server trying to blow the
    context budget or exfiltrate data by return value).
  - the client never grants filesystem/Docker access to itself - a stdio server only gets
    whatever `env`/working directory the caller (registry.py) explicitly configures.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
MAX_RESULT_BYTES = 512_000


class McpError(RuntimeError):
    pass


class McpTimeoutError(McpError):
    pass


class McpCircuitOpenError(McpError):
    pass


@dataclass
class McpToolDefinition:
    name: str
    description: str
    input_schema: dict


@dataclass
class McpCallResult:
    ok: bool
    content: Any
    error: str | None = None
    truncated: bool = False


class McpTransport(Protocol):
    async def request(self, method: str, params: dict, *, timeout_seconds: float) -> dict: ...
    async def close(self) -> None: ...


class StdioTransport:
    """One subprocess per server, reused across calls; newline-delimited JSON-RPC frames on
    stdin/stdout (the MCP stdio transport convention). A single asyncio.Lock serializes calls -
    correct and sufficient here since the orchestration engine only ever makes one capability
    call at a time per task."""

    def __init__(self, command: str, *, env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            # posix=True (shlex's default) treats backslash as an escape character and
            # silently eats every backslash in a raw Windows path (`C:\Users\...` becomes
            # `C:Users...`) - posix=False preserves them. Production always runs in Linux
            # containers, but a Windows dev/test environment must not silently mis-spawn.
            args = shlex.split(self._command, posix=(os.name != "nt"))
            if not args:
                raise McpError("empty stdio command")
            self._process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._env,
            )
        return self._process

    async def request(self, method: str, params: dict, *, timeout_seconds: float) -> dict:
        async with self._lock:
            process = await self._ensure_started()
            request_id = uuid.uuid4().hex
            frame = json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            assert process.stdin is not None
            process.stdin.write((frame + "\n").encode("utf-8"))
            await process.stdin.drain()
            assert process.stdout is not None
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout_seconds)
            except TimeoutError as exc:
                raise McpTimeoutError(
                    f"MCP stdio call {method!r} timed out after {timeout_seconds}s"
                ) from exc
            if not line:
                stderr_tail = b""
                if process.stderr is not None:
                    try:
                        stderr_tail = await asyncio.wait_for(process.stderr.read(4096), timeout=2)
                    except TimeoutError:
                        pass
                raise McpError(
                    f"MCP server process closed stdout unexpectedly "
                    f"(stderr: {stderr_tail.decode('utf-8', errors='replace')[:500]})"
                )
            try:
                response = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise McpError(f"MCP server returned non-JSON line: {line[:200]!r}") from exc
            if response.get("id") != request_id:
                raise McpError(
                    f"MCP response id mismatch: expected {request_id}, got {response.get('id')}"
                )
            return response

    async def close(self) -> None:
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()


class HttpTransport:
    def __init__(self, url: str) -> None:
        self._url = url

    async def request(self, method: str, params: dict, *, timeout_seconds: float) -> dict:
        request_id = uuid.uuid4().hex
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise McpTimeoutError(
                f"MCP HTTP call {method!r} timed out after {timeout_seconds}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise McpError(f"MCP HTTP call {method!r} failed: {exc}") from exc
        if data.get("id") != request_id:
            raise McpError("MCP HTTP response id mismatch")
        return data

    async def close(self) -> None:
        return None


class _CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def before_call(self) -> None:
        if self._opened_at is None:
            return
        if time.monotonic() - self._opened_at < self._reset_seconds:
            raise McpCircuitOpenError(
                "MCP server circuit open - failing fast until cooldown elapses"
            )

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._opened_at = time.monotonic()


class McpClient:
    def __init__(
        self,
        *,
        name: str,
        transport: McpTransport,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        self.name = name
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._breaker = _CircuitBreaker()
        self._initialized = False

    async def _call(self, method: str, params: dict) -> dict:
        self._breaker.before_call()
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._transport.request(
                    method, params, timeout_seconds=self._timeout_seconds
                )
                if "error" in response:
                    # A JSON-RPC application-level error is just as retryable as a transport
                    # failure from this client's point of view (e.g. a server reporting
                    # transient unavailability) - route it through the same except/backoff
                    # path below rather than raising immediately on attempt 1.
                    raise McpError(
                        f"MCP server {self.name} returned error for {method}: {response['error']}"
                    )
            except McpCircuitOpenError:
                raise
            except Exception as exc:  # noqa: BLE001 - any transport/protocol/RPC failure is retryable
                last_exc = exc
                self._breaker.record_failure()
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt * 0.5, 5))
                    continue
                raise McpError(
                    f"MCP call {self.name}.{method} failed after retries: {exc}"
                ) from exc
            else:
                self._breaker.record_success()
                return response.get("result", {}) or {}
        assert last_exc is not None  # pragma: no cover - loop always returns or raises above
        raise McpError(str(last_exc))

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._call(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "clientInfo": {"name": "airuntime", "version": "1.0"},
                "capabilities": {},
            },
        )
        self._initialized = True

    async def list_tools(self) -> list[McpToolDefinition]:
        await self.initialize()
        result = await self._call("tools/list", {})
        return [
            McpToolDefinition(
                name=raw["name"],
                description=raw.get("description", ""),
                input_schema=raw.get("inputSchema", {}),
            )
            for raw in result.get("tools", [])
        ]

    async def call_tool(self, name: str, arguments: dict) -> McpCallResult:
        await self.initialize()
        try:
            result = await self._call("tools/call", {"name": name, "arguments": arguments})
        except McpError as exc:
            return McpCallResult(ok=False, content=None, error=str(exc))
        content = result.get("content")
        serialized = json.dumps(content, default=str)
        truncated = False
        if len(serialized) > MAX_RESULT_BYTES:
            content = {"note": f"result exceeded {MAX_RESULT_BYTES} bytes and was dropped"}
            truncated = True
        return McpCallResult(
            ok=not result.get("isError", False), content=content, truncated=truncated
        )

    async def close(self) -> None:
        await self._transport.close()
