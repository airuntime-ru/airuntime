from __future__ import annotations

import shutil
import subprocess
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from src.core.config import settings

try:
    from redis import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ProjectVersion:
    commit_hash: str
    created_at: datetime
    message: str


class ProjectGitError(RuntimeError):
    pass


def _require_git() -> str:
    git_bin = shutil.which("git")
    if not git_bin:
        raise ProjectGitError("git is not available in container")
    return git_bin


def project_repo_dir(project_id: UUID | str) -> Path:
    return Path(settings.generated_projects_dir).resolve() / str(project_id)


def _normalize_repo_rel_path(value: str) -> str:
    """
    Normalize path inside git repo (no leading slash), prevent traversal.
    Returns empty string for root.
    """
    raw = (value or "").strip()
    raw = raw.replace("\\", "/")
    raw = raw.lstrip("/")
    if raw in {"", "."}:
        return ""
    parts = [p for p in raw.split("/") if p]
    if any(p == ".." for p in parts):
        raise ProjectGitError("Invalid path")
    return "/".join(parts)


@dataclass(frozen=True)
class ProjectVersionTreeEntry:
    name: str
    entry_type: str  # 'tree' | 'blob'
    size_bytes: int | None


def _run_git(*, cwd: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    _ = _require_git()
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=check,
    )


def _run_git_bytes(
    *, cwd: Path, args: list[str], check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    _ = _require_git()
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
    )


def init_repo_if_needed(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    if (project_dir / ".git").exists():
        return

    _ = _require_git()
    # Initialize repository.
    _run_git(cwd=project_dir, args=["init", "-q"])
    # Configure committer identity (we don't rely on global gitconfig inside container).
    _run_git(
        cwd=project_dir,
        args=["config", "user.email", "airuntime@local.invalid"],
        check=True,
    )
    _run_git(
        cwd=project_dir,
        args=["config", "user.name", "AIRuntime"],
        check=True,
    )


def _redis() -> Redis | None:
    if Redis is None:
        return None
    try:
        return Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    except Exception:
        return None


def _lock_key(project_id: str) -> str:
    return f"airuntime:git-lock:{project_id}"


class _NullLock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def with_project_git_lock(
    project_id: UUID | str, *, ttl_seconds: int = 180
) -> AbstractContextManager[None]:
    """
    Best-effort lock to protect git checkout/commit and docker builds.

    If Redis is unavailable, it degrades to a no-op lock.
    """
    lock = _redis()
    if not lock:
        return _NullLock()

    token = str(uuid4())
    key = _lock_key(str(project_id))
    acquired = False

    try:
        # Try acquire for a short time to reduce conflicts.
        for _ in range(30):
            acquired = bool(lock.set(key, token, nx=True, ex=ttl_seconds))
            if acquired:
                break
            time.sleep(0.2)
        if not acquired:
            return _NullLock()

        class _Releaser(_NullLock):
            def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
                try:
                    if lock.get(key) == token:
                        lock.delete(key)
                except Exception:
                    pass
                return None

        return _Releaser()
    except Exception:
        return _NullLock()


def _short_message(msg: str, *, max_len: int = 80) -> str:
    cleaned = " ".join((msg or "").replace("\n", " ").split())
    return cleaned[:max_len] if cleaned else "AIRuntime update"


def commit_snapshot(project_dir: Path, *, message: str) -> str | None:
    """
    Commit all current files inside project_dir into git.

    Returns new commit hash, or None when nothing changed.
    """
    with with_project_git_lock(project_dir.name):
        init_repo_if_needed(project_dir)

        # Add everything (excluding .git itself).
        _run_git(cwd=project_dir, args=["add", "-A"])

        # If index == HEAD, git commit will be a no-op (we also avoid creating noise).
        changed = _run_git(
            cwd=project_dir, args=["status", "--porcelain"], check=False
        ).stdout.strip()
        if not changed:
            return None

        completed = _run_git(
            cwd=project_dir,
            args=["commit", "-q", "-m", _short_message(message)],
            check=False,
        )
        if completed.returncode != 0:
            # If there's some race / unusual state, bubble up.
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            raise ProjectGitError(f"git commit failed: {stderr or stdout}")

        # Get HEAD hash.
        head = _run_git(cwd=project_dir, args=["rev-parse", "HEAD"]).stdout.strip()
        return head


def list_versions(project_dir: Path, *, limit: int = 30) -> list[ProjectVersion]:
    if not (project_dir / ".git").exists():
        return []

    fmt = "%H|%ct|%s"
    proc = _run_git(cwd=project_dir, args=["log", f"-n{int(limit)}", f"--pretty=format:{fmt}"])
    out = proc.stdout.strip()
    if not out:
        return []

    versions: list[ProjectVersion] = []
    for line in out.splitlines():
        commit_hash, unix_ct, msg = line.split("|", 2)
        created_at = datetime.fromtimestamp(int(unix_ct), tz=UTC)
        versions.append(ProjectVersion(commit_hash=commit_hash, created_at=created_at, message=msg))
    return versions


def list_version_tree(
    project_dir: Path, *, commit_hash: str, rel_path: str = ""
) -> list[ProjectVersionTreeEntry]:
    if not (project_dir / ".git").exists():
        raise ProjectGitError("Repo not initialized")

    normalized = _normalize_repo_rel_path(rel_path)

    # `git ls-tree <commit>:<path>` returns direct children with names relative to
    # that path. Using `-- <path>` returns prefixed names like `public/index.html`,
    # which makes the UI accidentally build paths such as `public/public/...`.
    if normalized:
        args = ["ls-tree", "-z", "-l", f"{commit_hash}:{normalized}"]
    else:
        args = ["ls-tree", "-z", "-l", commit_hash]

    proc = _run_git_bytes(cwd=project_dir, args=args, check=False)
    if proc.returncode != 0:
        raise ProjectGitError(
            proc.stderr.decode("utf-8", errors="replace").strip() or "git ls-tree failed"
        )

    out = proc.stdout
    entries: list[ProjectVersionTreeEntry] = []
    for raw_item in out.split(b"\0"):
        if not raw_item:
            continue
        # Format: "<mode> <type> <object> <size>\t<name>"
        try:
            meta, name = raw_item.split(b"\t", 1)
        except ValueError:
            continue
        meta_parts = meta.split()
        if len(meta_parts) < 4:
            continue
        entry_type = meta_parts[1].decode("utf-8", errors="replace")
        size_bytes_raw = meta_parts[3].decode("utf-8", errors="replace")
        size_bytes = None if size_bytes_raw == "-" else int(size_bytes_raw)
        entries.append(
            ProjectVersionTreeEntry(
                name=name.decode("utf-8", errors="replace"),
                entry_type=entry_type,
                size_bytes=size_bytes,
            )
        )

    # Sort: directories first, then name.
    entries.sort(key=lambda e: (0 if e.entry_type == "tree" else 1, e.name.lower()))
    return entries


def read_version_file(
    project_dir: Path,
    *,
    commit_hash: str,
    rel_path: str,
    max_bytes: int = 256 * 1024,
) -> dict:
    """
    Return file content for viewing.
    For binary/unsupported files -> is_binary=true, content="".
    For too large files -> truncated=true.
    """
    if not (project_dir / ".git").exists():
        raise ProjectGitError("Repo not initialized")

    normalized = _normalize_repo_rel_path(rel_path)
    if not normalized:
        raise ProjectGitError("Path points to directory")

    obj = f"{commit_hash}:{normalized}"
    proc = _run_git_bytes(cwd=project_dir, args=["show", obj], check=False)
    if proc.returncode != 0:
        raise ProjectGitError(
            proc.stderr.decode("utf-8", errors="replace").strip() or "git show failed"
        )

    data = proc.stdout
    size_bytes = len(data)
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True

    # Quick binary detection.
    if b"\0" in data[: min(4096, len(data))]:
        return {
            "content": "",
            "is_binary": True,
            "truncated": truncated,
            "size_bytes": size_bytes,
        }

    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        # Still allow "replace" to show something instead of crashing.
        try:
            content = data.decode("utf-8", errors="replace")
        except Exception:
            return {
                "content": "",
                "is_binary": True,
                "truncated": truncated,
                "size_bytes": size_bytes,
            }

    return {
        "content": content,
        "is_binary": False,
        "truncated": truncated,
        "size_bytes": size_bytes,
    }


def archive_version(project_dir: Path, *, commit_hash: str, out_path: Path) -> None:
    if not (project_dir / ".git").exists():
        raise ProjectGitError("Repo not initialized")

    try:
        proc = _run_git_bytes(cwd=project_dir, args=["archive", "--format=zip", commit_hash])
    except subprocess.CalledProcessError as exc:
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes | bytearray)
            else str(exc.stderr)
        )
        raise ProjectGitError(stderr.strip() or "git archive failed") from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(proc.stdout)


def archive_version_stream(project_dir: Path, *, commit_hash: str) -> bytes:
    # Helper for smaller archives.
    try:
        proc = _run_git_bytes(cwd=project_dir, args=["archive", "--format=zip", commit_hash])
    except subprocess.CalledProcessError as exc:
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes | bytearray)
            else str(exc.stderr)
        )
        raise ProjectGitError(stderr.strip() or "git archive failed") from exc
    return proc.stdout


def rollback_to(project_dir: Path, *, commit_hash: str, message: str) -> str:
    """
    Checkout target commit and create a new commit representing rollback.
    Returns new HEAD hash.
    """
    if not (project_dir / ".git").exists():
        raise ProjectGitError("Repo not initialized")

    with with_project_git_lock(project_dir.name):
        try:
            _run_git(cwd=project_dir, args=["checkout", "-q", "--force", commit_hash])
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else str(exc.stderr)
            raise ProjectGitError(stderr or "git checkout failed") from exc

        # Create explicit rollback commit even if checkout resulted in same tree.
        _run_git(
            cwd=project_dir,
            args=["commit", "-q", "--allow-empty", "-m", _short_message(message)],
            check=False,
        )

        try:
            return _run_git(cwd=project_dir, args=["rev-parse", "HEAD"]).stdout.strip()
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else str(exc.stderr)
            raise ProjectGitError(stderr or "git rev-parse failed") from exc
