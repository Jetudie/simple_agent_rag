"""Command-line interface."""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_config
from .runner import AgentRunError, GoalAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goal-agent",
        description="Persistently work toward GOALS.md and independently verify PASS_CRITERIA.md.",
    )
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to the TOML configuration file (default: config.toml)",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and required prompt/goal files without calling the API",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.check_config:
            required = {
                "global prompt": config.workspace.agents_file,
                "goals": config.workspace.goals_file,
                "pass criteria": config.workspace.criteria_file,
            }
            for label, name in required.items():
                path = config.workspace.path_for(name)
                if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                    raise ConfigError(f"Required {label} file is missing or empty: {path}")
            print(f"Configuration is valid. Workspace: {config.workspace.root}")
            print(f"Model: {config.api.model}; API: {config.api.base_url}")
            print(
                f"Limits: {config.run.max_loops} loops, {config.run.max_time_seconds:g}s total, "
                f"{config.run.delay_seconds:g}s delay"
            )
            return 0

        outcome = GoalAgent(config).run()
        print(
            f"[{outcome.status}] {outcome.message} "
            f"cycles={outcome.cycles} elapsed={outcome.elapsed_seconds:.1f}s run={outcome.run_id}"
        )
        return 0 if outcome.success else 1
    except (ConfigError, AgentRunError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
