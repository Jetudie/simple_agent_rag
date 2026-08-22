"""Workspace-confined tools exposed to the language model."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .config import ToolConfig


class ToolError(ValueError):
    """A safe, user-readable tool failure."""


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in the workspace. Hidden agent run logs are omitted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory, default '.'"},
                    "recursive": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or fully replace a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "Replace one exact text occurrence in a workspace file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                    "expected_replacements": {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run an allow-listed executable in the workspace without a shell.",
            "parameters": {
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Executable and arguments, e.g. ['python', '-m', 'unittest']",
                    },
                    "working_directory": {"type": "string", "default": "."},
                    "timeout_seconds": {"type": "number", "minimum": 0.1},
                },
                "required": ["argv"],
                "additionalProperties": False,
            },
        },
    },
]


class WorkspaceTools:
    def __init__(
        self,
        root: Path,
        config: ToolConfig,
        read_only: bool = False,
        protected_paths: Iterable[Path] = (),
    ) -> None:
        self.root = root.resolve()
        self.config = config
        self.read_only = read_only
        self.protected_paths = tuple(path.resolve() for path in protected_paths)

    @property
    def definitions(self) -> list[dict[str, Any]]:
        if not self.read_only:
            return TOOL_DEFINITIONS
        return [
            definition
            for definition in TOOL_DEFINITIONS
            if definition["function"]["name"] not in {"write_file", "replace_in_file"}
        ]

    def _resolve(self, raw_path: str, require_exists: bool = False) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ToolError("path must be a non-empty string")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolError(f"Path escapes workspace: {raw_path}") from exc
        if require_exists and not candidate.exists():
            raise ToolError(f"Path does not exist: {raw_path}")
        return candidate

    def _assert_writable(self, path: Path) -> None:
        for protected in self.protected_paths:
            if path == protected or protected in path.parents:
                relative = protected.relative_to(self.root).as_posix()
                raise ToolError(f"Orchestrator control path is protected from model writes: {relative}")

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "list_files":
                return self._list_files(**arguments)
            if name == "read_file":
                return self._read_file(**arguments)
            if name == "write_file":
                if self.read_only:
                    raise ToolError("Verification context cannot modify files")
                return self._write_file(**arguments)
            if name == "replace_in_file":
                if self.read_only:
                    raise ToolError("Verification context cannot modify files")
                return self._replace_in_file(**arguments)
            if name == "run_command":
                return self._run_command(**arguments)
            raise ToolError(f"Unknown tool: {name}")
        except TypeError as exc:
            raise ToolError(f"Invalid arguments for {name}: {exc}") from exc

    def _list_files(self, path: str = ".", recursive: bool = True) -> dict[str, Any]:
        directory = self._resolve(path, require_exists=True)
        if not directory.is_dir():
            raise ToolError(f"Not a directory: {path}")
        iterator = directory.rglob("*") if recursive else directory.glob("*")
        files: list[str] = []
        truncated = False
        for item in iterator:
            relative = item.relative_to(self.root)
            if relative.parts and relative.parts[0] == ".goal_agent":
                continue
            if item.is_file():
                files.append(relative.as_posix())
                if len(files) >= 1000:
                    truncated = True
                    break
        return {"files": sorted(files), "truncated": truncated}

    def _read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> dict[str, Any]:
        file_path = self._resolve(path, require_exists=True)
        if not file_path.is_file():
            raise ToolError(f"Not a file: {path}")
        if file_path.stat().st_size > self.config.max_file_bytes:
            raise ToolError(f"File exceeds max_file_bytes ({self.config.max_file_bytes})")
        if start_line < 1 or (end_line is not None and end_line < start_line):
            raise ToolError("Invalid line range")
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ToolError(f"File is not UTF-8 text: {path}") from exc
        selected = lines[start_line - 1 : end_line]
        numbered = "\n".join(
            f"{number}: {line}" for number, line in enumerate(selected, start=start_line)
        )
        return {
            "path": file_path.relative_to(self.root).as_posix(),
            "start_line": start_line,
            "end_line": start_line + len(selected) - 1 if selected else start_line - 1,
            "total_lines": len(lines),
            "content": numbered[: self.config.max_output_chars],
            "truncated": len(numbered) > self.config.max_output_chars,
        }

    def _write_file(self, path: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        encoded = content.encode("utf-8")
        if len(encoded) > self.config.max_file_bytes:
            raise ToolError(f"Content exceeds max_file_bytes ({self.config.max_file_bytes})")
        file_path = self._resolve(path)
        self._assert_writable(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"path": file_path.relative_to(self.root).as_posix(), "bytes_written": len(encoded)}

    def _replace_in_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        expected_replacements: int = 1,
    ) -> dict[str, Any]:
        file_path = self._resolve(path, require_exists=True)
        self._assert_writable(file_path)
        if expected_replacements < 1:
            raise ToolError("expected_replacements must be positive")
        content = file_path.read_text(encoding="utf-8")
        actual = content.count(old_text)
        if actual != expected_replacements:
            raise ToolError(
                f"Expected {expected_replacements} exact occurrence(s), found {actual}; file unchanged"
            )
        updated = content.replace(old_text, new_text)
        if len(updated.encode("utf-8")) > self.config.max_file_bytes:
            raise ToolError(f"Updated file exceeds max_file_bytes ({self.config.max_file_bytes})")
        file_path.write_text(updated, encoding="utf-8")
        return {"path": file_path.relative_to(self.root).as_posix(), "replacements": actual}

    def _run_command(
        self,
        argv: list[str],
        working_directory: str = ".",
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.config.allow_commands:
            raise ToolError("Commands are disabled in config.toml")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
            raise ToolError("argv must be a non-empty array of strings")
        executable = Path(argv[0]).name.lower()
        if executable.endswith(".exe"):
            executable = executable[:-4]
        allowed = {item.removesuffix(".exe").lower() for item in self.config.allowed_commands}
        if executable not in allowed:
            raise ToolError(
                f"Command {argv[0]!r} is not allow-listed; allowed commands: {sorted(allowed)}"
            )
        cwd = self._resolve(working_directory, require_exists=True)
        if not cwd.is_dir():
            raise ToolError(f"Working directory is not a directory: {working_directory}")
        timeout = min(
            float(timeout_seconds or self.config.command_timeout_seconds),
            self.config.command_timeout_seconds,
        )
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                env=os.environ.copy(),
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            return {
                "argv": argv,
                "exit_code": completed.returncode,
                "stdout": stdout[: self.config.max_output_chars],
                "stderr": stderr[: self.config.max_output_chars],
                "output_truncated": (
                    len(stdout) > self.config.max_output_chars
                    or len(stderr) > self.config.max_output_chars
                ),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "argv": argv,
                "timed_out": True,
                "timeout_seconds": timeout,
                "stdout": (exc.stdout or "")[: self.config.max_output_chars],
                "stderr": (exc.stderr or "")[: self.config.max_output_chars],
            }
        except OSError as exc:
            raise ToolError(f"Could not start command {argv[0]!r}: {exc}") from exc


def tool_result_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
