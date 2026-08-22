"""Configuration loading and validation."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the agent configuration is invalid."""


_ENV_PATTERN = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")


def _expand_env(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        if name not in os.environ:
            raise ConfigError(f"Environment variable {name!r} is required but not set")
        return os.environ[name]

    return _ENV_PATTERN.sub(replace, value)


def _table(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a TOML table")
    return value


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 120.0
    max_retries: int = 3
    temperature: float | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RunConfig:
    max_loops: int = 8
    delay_seconds: float = 5.0
    max_time_seconds: float = 3600.0
    max_turns_per_phase: int = 30


@dataclass(frozen=True)
class WorkspaceConfig:
    root: Path
    agents_file: str = "AGENTS.md"
    goals_file: str = "GOALS.md"
    criteria_file: str = "PASS_CRITERIA.md"
    handover_file: str = "HANDOVER.md"
    feedback_file: str = "VERIFICATION_FEEDBACK.md"
    state_dir: str = ".goal_agent"

    def path_for(self, relative_name: str) -> Path:
        candidate = (self.root / relative_name).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ConfigError(f"Configured path escapes workspace: {relative_name}") from exc
        return candidate


@dataclass(frozen=True)
class ToolConfig:
    allow_commands: bool = True
    command_timeout_seconds: float = 120.0
    max_output_chars: int = 30_000
    max_file_bytes: int = 1_000_000
    allowed_commands: tuple[str, ...] = (
        "python",
        "python3",
        "py",
        "pytest",
        "git",
        "node",
        "npm",
        "npx",
    )


@dataclass(frozen=True)
class AgentConfig:
    source: Path
    api: ApiConfig
    run: RunConfig
    workspace: WorkspaceConfig
    tools: ToolConfig


def load_config(path: str | Path) -> AgentConfig:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigError(f"Configuration file not found: {source}")

    try:
        with source.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {source}: {exc}") from exc

    api_data = _table(data, "api")
    run_data = _table(data, "run")
    workspace_data = _table(data, "workspace")
    tools_data = _table(data, "tools")

    try:
        base_url = _expand_env(str(api_data["base_url"])).strip().rstrip("/")
        api_key = _expand_env(str(api_data["api_key"])).strip()
        model = _expand_env(str(api_data["model"])).strip()
    except KeyError as exc:
        raise ConfigError(f"Missing required [api] setting: {exc.args[0]}") from exc

    if not base_url or not api_key or not model:
        raise ConfigError("[api] base_url, api_key, and model must not be empty")
    if api_key in {"YOUR_API_KEY", "replace-me", "changeme"}:
        raise ConfigError("Replace the placeholder [api].api_key before running the agent")

    extra_headers_raw = api_data.get("extra_headers", {})
    if not isinstance(extra_headers_raw, dict):
        raise ConfigError("[api].extra_headers must be a TOML inline table")
    extra_headers = {str(key): _expand_env(str(value)) for key, value in extra_headers_raw.items()}

    root_value = _expand_env(str(workspace_data.get("root", ".")))
    root = Path(root_value).expanduser()
    if not root.is_absolute():
        root = source.parent / root
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError(f"Workspace root does not exist or is not a directory: {root}")

    api = ApiConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=float(api_data.get("timeout_seconds", 120)),
        max_retries=int(api_data.get("max_retries", 3)),
        temperature=(
            None if api_data.get("temperature") is None else float(api_data["temperature"])
        ),
        extra_headers=extra_headers,
    )
    run = RunConfig(
        max_loops=int(run_data.get("max_loops", 8)),
        delay_seconds=float(run_data.get("delay_seconds", 5)),
        max_time_seconds=float(run_data.get("max_time_seconds", 3600)),
        max_turns_per_phase=int(run_data.get("max_turns_per_phase", 30)),
    )
    workspace = WorkspaceConfig(
        root=root,
        agents_file=str(workspace_data.get("agents_file", "AGENTS.md")),
        goals_file=str(workspace_data.get("goals_file", "GOALS.md")),
        criteria_file=str(workspace_data.get("criteria_file", "PASS_CRITERIA.md")),
        handover_file=str(workspace_data.get("handover_file", "HANDOVER.md")),
        feedback_file=str(workspace_data.get("feedback_file", "VERIFICATION_FEEDBACK.md")),
        state_dir=str(workspace_data.get("state_dir", ".goal_agent")),
    )
    allowed_raw = tools_data.get("allowed_commands", list(ToolConfig.allowed_commands))
    if not isinstance(allowed_raw, list) or not all(isinstance(item, str) for item in allowed_raw):
        raise ConfigError("[tools].allowed_commands must be an array of strings")
    tools = ToolConfig(
        allow_commands=bool(tools_data.get("allow_commands", True)),
        command_timeout_seconds=float(tools_data.get("command_timeout_seconds", 120)),
        max_output_chars=int(tools_data.get("max_output_chars", 30_000)),
        max_file_bytes=int(tools_data.get("max_file_bytes", 1_000_000)),
        allowed_commands=tuple(item.lower() for item in allowed_raw),
    )

    if api.timeout_seconds <= 0 or api.max_retries < 0:
        raise ConfigError("API timeout must be positive and max_retries cannot be negative")
    if run.max_loops <= 0 or run.max_turns_per_phase <= 0:
        raise ConfigError("max_loops and max_turns_per_phase must be positive")
    if run.delay_seconds < 0 or run.max_time_seconds <= 0:
        raise ConfigError("delay_seconds cannot be negative and max_time_seconds must be positive")
    if tools.command_timeout_seconds <= 0 or tools.max_output_chars <= 0 or tools.max_file_bytes <= 0:
        raise ConfigError("Tool timeout and size limits must be positive")

    for configured_path in (
        workspace.agents_file,
        workspace.goals_file,
        workspace.criteria_file,
        workspace.handover_file,
        workspace.feedback_file,
        workspace.state_dir,
    ):
        workspace.path_for(configured_path)

    return AgentConfig(source=source, api=api, run=run, workspace=workspace, tools=tools)

