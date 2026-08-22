"""OpenCode CLI backend for achievement and verification phases."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .client import ApiError, ChatResponse
from .config import OpenCodeConfig


class OpenCodeError(ApiError):
    """Raised when the OpenCode CLI cannot complete a phase."""


def resolve_executable(command: str) -> str:
    """Resolve a command name or explicit executable path without invoking a shell."""
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate.resolve()
        if not resolved.is_file():
            raise OpenCodeError(f"OpenCode executable not found: {resolved}")
        return str(resolved)
    found = shutil.which(command)
    if not found:
        raise OpenCodeError(
            f"OpenCode executable {command!r} was not found on PATH. "
            "Install OpenCode or set [opencode].executable."
        )
    return found


def render_messages(messages: list[dict[str, Any]]) -> str:
    """Render chat messages into one self-contained OpenCode run prompt."""
    blocks: list[str] = []
    for message in messages:
        role = str(message.get("role", "unknown")).upper()
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        blocks.append(f"## {role}\n\n{content}")
    return "\n\n---\n\n".join(blocks)


class OpenCodeClient:
    """Adapter exposing OpenCode's non-interactive CLI through the chat-client interface."""

    def __init__(self, config: OpenCodeConfig, workspace: Path) -> None:
        self.config = config
        self.workspace = workspace.resolve()
        self.executable = resolve_executable(config.executable)

    @property
    def timeout_seconds(self) -> float:
        return self.config.timeout_seconds

    def build_command(self, prompt: str, phase: str) -> list[str]:
        command = [self.executable, "run"]
        if self.config.server_url:
            command.extend(["--attach", self.config.server_url])
        if self.config.model:
            command.extend(["--model", self.config.model])
        selected_agent = (
            self.config.verifier_agent or self.config.agent
            if phase == "verification"
            else self.config.agent
        )
        if selected_agent:
            command.extend(["--agent", selected_agent])
        command.extend(["--dir", str(self.workspace)])
        if self.config.auto_approve:
            command.append("--auto")
        command.extend(self.config.extra_args)
        command.append(prompt)
        return command

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_seconds: float | None = None,
        phase: str = "achievement",
    ) -> ChatResponse:
        del tools  # OpenCode supplies and executes its own tools.
        prompt = render_messages(messages)
        command = self.build_command(prompt, phase)
        timeout = min(float(timeout_seconds or self.config.timeout_seconds), self.config.timeout_seconds)
        environment = os.environ.copy()
        environment.setdefault("NO_COLOR", "1")
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                stdin=subprocess.DEVNULL,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode("utf-8", errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr = (
                exc.stderr.decode("utf-8", errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            detail = (stderr or stdout).strip()
            raise OpenCodeError(
                f"OpenCode {phase} phase timed out after {timeout:g}s"
                + (f": {detail[-2000:]}" if detail else "")
            ) from exc
        except OSError as exc:
            raise OpenCodeError(f"Could not start OpenCode: {exc}") from exc

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            detail = stderr or stdout or "No diagnostic output"
            raise OpenCodeError(
                f"OpenCode {phase} phase exited with code {completed.returncode}: {detail[-4000:]}"
            )
        if not stdout:
            raise OpenCodeError(
                f"OpenCode {phase} phase returned empty stdout"
                + (f": {stderr[-2000:]}" if stderr else "")
            )
        return ChatResponse(message={"role": "assistant", "content": stdout}, usage={})
