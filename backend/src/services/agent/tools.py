"""Workspace tools exposed to the coding agent.

Deliberately small and explicit (per the platform's security architecture:
"LLM tool execution allowlist - explicitly registered tools only"). There is
no generic shell/exec tool here: the model can inspect and edit files, and
separately the build/test step (src/services/artifacts.py) actually builds
the project in Docker and reports back real errors. Keeping "edit" and
"execute" as separate stages keeps the blast radius of a single tool call
small and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.workspace import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    WorkspaceError,
    list_workspace_files,
    resolve_in_workspace,
    workspace_size_bytes,
)

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_files",
        "description": (
            "List files that currently exist in the project workspace. Always call this "
            "before writing files so you know what already exists and avoid clobbering it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative subdirectory to list, default '.' (whole project).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "Read the full current contents of one file in the project workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path."}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file, or completely replace the contents of an existing file. "
            "Use this for new files or full rewrites; use edit_file for small, targeted changes "
            "to an existing file so you don't have to resend the whole file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "content": {"type": "string", "description": "Full UTF-8 file content."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Make a precise, incremental edit to an existing file by replacing one exact, "
            "unique occurrence of old_text with new_text. Fails if old_text is not found or "
            "is not unique in the file - in that case include more surrounding context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "old_text": {"type": "string", "description": "Exact existing snippet to replace."},
                "new_text": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the project workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path."}},
            "required": ["path"],
        },
    },
]

TOOL_NAMES = {tool["name"] for tool in TOOL_DEFS}


@dataclass
class ToolExecutionResult:
    ok: bool
    summary: str
    content: str = ""


class WorkspaceTools:
    """Executes agent tool calls against one project's workspace directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.touched_files: set[str] = set()

    def call(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        try:
            if name == "list_files":
                return self._list_files(arguments.get("path", "."))
            if name == "read_file":
                return self._read_file(str(arguments.get("path", "")))
            if name == "write_file":
                return self._write_file(str(arguments.get("path", "")), arguments.get("content", ""))
            if name == "edit_file":
                return self._edit_file(
                    str(arguments.get("path", "")),
                    arguments.get("old_text", ""),
                    arguments.get("new_text", ""),
                )
            if name == "delete_file":
                return self._delete_file(str(arguments.get("path", "")))
            return ToolExecutionResult(ok=False, summary=f"Unknown tool: {name}")
        except WorkspaceError as exc:
            return ToolExecutionResult(ok=False, summary=str(exc))
        except Exception as exc:  # defensive: never let a tool crash the agent loop
            return ToolExecutionResult(ok=False, summary=f"Tool error: {exc}")

    def _list_files(self, path: str) -> ToolExecutionResult:
        if path and path != ".":
            base = resolve_in_workspace(self.root, path)
            if not base.exists():
                return ToolExecutionResult(ok=True, summary="Directory does not exist yet.", content="[]")
            files = [
                p.relative_to(self.root).as_posix()
                for p in sorted(base.rglob("*"))
                if p.is_file() and ".git" not in p.parts and ".airuntime" not in p.parts
            ]
        else:
            files = list_workspace_files(self.root)
        content = "\n".join(files) if files else "(empty workspace)"
        return ToolExecutionResult(ok=True, summary=f"{len(files)} file(s)", content=content)

    def _read_file(self, path: str) -> ToolExecutionResult:
        target = resolve_in_workspace(self.root, path)
        if not target.exists() or not target.is_file():
            return ToolExecutionResult(ok=False, summary=f"File not found: {path}")
        data = target.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            return ToolExecutionResult(
                ok=False, summary=f"File is too large to read ({len(data)} bytes)"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolExecutionResult(ok=False, summary="File is not valid UTF-8 text")
        return ToolExecutionResult(ok=True, summary=f"Read {path} ({len(data)} bytes)", content=text)

    def _write_file(self, path: str, content: Any) -> ToolExecutionResult:
        if not isinstance(content, str):
            return ToolExecutionResult(ok=False, summary="content must be a string")
        target = resolve_in_workspace(self.root, path)
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            return ToolExecutionResult(ok=False, summary=f"File too large ({len(encoded)} bytes)")
        current_total = workspace_size_bytes(self.root)
        existing = target.stat().st_size if target.exists() else 0
        if current_total - existing + len(encoded) > MAX_TOTAL_BYTES:
            return ToolExecutionResult(ok=False, summary="Project workspace size limit exceeded")
        existing_files = set(list_workspace_files(self.root))
        rel = target.relative_to(self.root).as_posix()
        if rel not in existing_files and len(existing_files) >= MAX_FILES:
            return ToolExecutionResult(ok=False, summary=f"Too many files in project (max {MAX_FILES})")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Wrote {rel} ({len(encoded)} bytes)")

    def _edit_file(self, path: str, old_text: Any, new_text: Any) -> ToolExecutionResult:
        if not isinstance(old_text, str) or not old_text:
            return ToolExecutionResult(ok=False, summary="old_text must be a non-empty string")
        if not isinstance(new_text, str):
            return ToolExecutionResult(ok=False, summary="new_text must be a string")
        target = resolve_in_workspace(self.root, path)
        if not target.exists():
            return ToolExecutionResult(
                ok=False, summary=f"File not found: {path}. Use write_file to create it first."
            )
        current = target.read_text(encoding="utf-8")
        count = current.count(old_text)
        if count == 0:
            return ToolExecutionResult(
                ok=False,
                summary="old_text not found in file - re-read the file, it may have changed",
            )
        if count > 1:
            return ToolExecutionResult(
                ok=False,
                summary=f"old_text is not unique ({count} occurrences) - include more context",
            )
        updated = current.replace(old_text, new_text, 1)
        encoded = updated.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            return ToolExecutionResult(ok=False, summary="Resulting file would be too large")
        target.write_text(updated, encoding="utf-8")
        rel = target.relative_to(self.root).as_posix()
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Edited {rel}")

    def _delete_file(self, path: str) -> ToolExecutionResult:
        target = resolve_in_workspace(self.root, path)
        if not target.exists():
            return ToolExecutionResult(ok=False, summary=f"File not found: {path}")
        target.unlink()
        rel = target.relative_to(self.root).as_posix()
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Deleted {rel}")
