"""The persistent achievement/verification orchestration loop."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .client import ApiError, OpenAICompatibleClient
from .config import AgentConfig, ConfigError
from .journal import RunJournal
from .opencode_client import OpenCodeClient
from .prompts import ACHIEVER_SYSTEM, VERIFIER_SYSTEM, achiever_prompt, verifier_prompt
from .tools import ToolError, WorkspaceTools, tool_result_json


class AgentRunError(RuntimeError):
    """Raised for a fatal orchestration error."""


@dataclass(frozen=True)
class RunOutcome:
    success: bool
    status: str
    cycles: int
    elapsed_seconds: float
    run_id: str
    message: str


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first decodable JSON object from plain or fenced model output."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Model returned empty final content")
    stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    decoder = json.JSONDecoder()
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Model final response did not contain a valid JSON object")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def markdown_requirements(markdown: str) -> list[str]:
    """Turn a Markdown list, or fallback paragraphs, into independently checkable items."""
    items: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$", line)
        if match:
            item = re.sub(r"^\[[ xX]\]\s*", "", match.group(1)).strip()
            if item:
                items.append(item)
    if items:
        return items

    paragraphs = re.split(r"\n\s*\n", markdown)
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        lines = [line for line in lines if not line.startswith("#")]
        if lines:
            items.append(" ".join(lines))
    return items


def labeled_requirements(items: list[str], prefix: str) -> str:
    return "\n".join(f"- {prefix}{index}: {item}" for index, item in enumerate(items, start=1))


def normalize_achievement(raw: dict[str, Any]) -> dict[str, Any]:
    status = raw.get("status")
    if status not in {"ready_for_verification", "blocked"}:
        status = "blocked"
    return {
        "status": status,
        "summary": str(raw.get("summary", "No summary returned.")).strip(),
        "completed": _string_list(raw.get("completed")),
        "todos": _string_list(raw.get("todos")),
        "tests": _string_list(raw.get("tests")),
        "risks": _string_list(raw.get("risks")),
    }


def _normalize_checks(
    raw_items: Any,
    expected: list[str],
    prefix: str,
    text_key: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    supplied: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item_id = str(raw_item.get("id", "")).strip().upper()
            if item_id in supplied:
                duplicates.add(item_id)
            elif item_id:
                supplied[item_id] = raw_item

    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    for index, expected_text in enumerate(expected, start=1):
        item_id = f"{prefix}{index}"
        item = supplied.get(item_id)
        if item is None:
            checks.append(
                {
                    "id": item_id,
                    text_key: expected_text,
                    "passed": False,
                    "evidence": "Verifier omitted this required check.",
                    "feedback": f"Independently verify and report {item_id}.",
                }
            )
            issues.append(f"Verifier omitted required check {item_id}.")
            continue
        duplicated = item_id in duplicates
        checks.append(
            {
                "id": item_id,
                text_key: expected_text,
                "passed": item.get("passed") is True and not duplicated,
                "evidence": str(item.get("evidence", "No evidence returned.")).strip(),
                "feedback": (
                    f"Verifier returned duplicate entries for {item_id}; verify it once unambiguously."
                    if duplicated
                    else str(item.get("feedback", "")).strip()
                ),
            }
        )
        if duplicated:
            issues.append(f"Verifier returned duplicate check {item_id}.")
    return checks, issues


def normalize_verification(
    raw: dict[str, Any],
    expected_targets: list[str] | None = None,
    expected_criteria: list[str] | None = None,
) -> dict[str, Any]:
    expected_targets = expected_targets or []
    expected_criteria = expected_criteria or []
    targets, target_issues = _normalize_checks(raw.get("targets"), expected_targets, "G", "target")
    criteria, criterion_issues = _normalize_checks(
        raw.get("criteria"), expected_criteria, "C", "criterion"
    )
    all_targets_passed = bool(targets) and all(item["passed"] for item in targets)
    all_criteria_passed = bool(criteria) and all(item["passed"] for item in criteria)
    passed = raw.get("passed") is True and all_targets_passed and all_criteria_passed
    feedback = _string_list(raw.get("feedback"))
    feedback.extend(target_issues)
    feedback.extend(criterion_issues)
    if not expected_targets:
        feedback.append("No normalized targets were available; add at least one target to GOALS.md.")
    if not expected_criteria:
        feedback.append("No normalized criteria were available; add at least one item to PASS_CRITERIA.md.")
    if raw.get("passed") is True and not (all_targets_passed and all_criteria_passed):
        feedback.append("Overall pass was inconsistent with required checks; resolve every failed item.")
    return {
        "passed": passed,
        "summary": str(raw.get("summary", "No verification summary returned.")).strip(),
        "targets": targets,
        "criteria": criteria,
        "feedback": feedback,
    }


class GoalAgent:
    def __init__(
        self,
        config: AgentConfig,
        client: OpenAICompatibleClient | Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        output: Callable[[str], None] = print,
    ) -> None:
        self.config = config
        if client is not None:
            self.client = client
        elif config.backend == "opencode":
            self.client = OpenCodeClient(config.opencode, config.workspace.root)
        else:
            if config.api is None:
                raise ConfigError("API backend selected without an [api] configuration")
            self.client = OpenAICompatibleClient(config.api)
        self.clock = clock
        self.sleeper = sleeper
        self.output = output

    def _required_text(self, configured_name: str, label: str) -> str:
        path = self.config.workspace.path_for(configured_name)
        if not path.is_file():
            raise ConfigError(f"{label} file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ConfigError(f"{label} file is empty: {path}")
        return text

    def _optional_text(self, configured_name: str, default: str) -> str:
        path = self.config.workspace.path_for(configured_name)
        return path.read_text(encoding="utf-8").strip() if path.is_file() else default

    def _phase(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: WorkspaceTools,
        deadline: float,
        phase: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for _ in range(self.config.run.max_turns_per_phase):
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError("Run time limit reached during model phase")
            backend_timeout = (
                self.config.opencode.timeout_seconds
                if self.config.backend == "opencode"
                else self.config.api.timeout_seconds if self.config.api is not None else remaining
            )
            response = self.client.chat(
                messages,
                tools.definitions,
                timeout_seconds=min(backend_timeout, max(0.1, remaining)),
                phase=phase,
            )
            message = response.message
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.get("content"),
            }
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            messages.append(assistant_message)

            if not tool_calls:
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise AgentRunError("Model returned neither tool calls nor final content")
                return content, messages

            for tool_call in tool_calls:
                call_id = str(tool_call.get("id", "missing-tool-call-id"))
                function = tool_call.get("function") or {}
                name = str(function.get("name", ""))
                try:
                    raw_arguments = function.get("arguments") or "{}"
                    arguments = (
                        raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments)
                    )
                    if not isinstance(arguments, dict):
                        raise ToolError("Tool arguments must decode to a JSON object")
                    if name == "run_command":
                        arguments = dict(arguments)
                        command_remaining = deadline - self.clock()
                        if command_remaining <= 0:
                            raise TimeoutError("Run time limit reached before command execution")
                        requested_timeout = float(
                            arguments.get(
                                "timeout_seconds", self.config.tools.command_timeout_seconds
                            )
                        )
                        arguments["timeout_seconds"] = min(requested_timeout, command_remaining)
                    result = {"ok": True, "result": tools.execute(name, arguments)}
                except TimeoutError:
                    raise
                except (json.JSONDecodeError, ToolError, TypeError, ValueError) as exc:
                    result = {"ok": False, "error": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": tool_result_json(result),
                    }
                )
        raise AgentRunError(
            f"Model exceeded max_turns_per_phase ({self.config.run.max_turns_per_phase})"
        )

    def run(self) -> RunOutcome:
        started = self.clock()
        deadline = started + self.config.run.max_time_seconds
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        journal = RunJournal(self.config.workspace, run_id)
        cycle = 0
        latest_achievement: dict[str, Any] = {
            "status": "blocked",
            "summary": "No achievement shift completed yet.",
            "completed": [],
            "todos": ["Start the first achievement shift."],
            "tests": [],
            "risks": [],
        }
        latest_verification: dict[str, Any] | None = None
        journal.write_state({"status": "running", "cycle": 0, "started_at_monotonic": started})

        try:
            for cycle in range(1, self.config.run.max_loops + 1):
                if self.clock() >= deadline:
                    return self._stop(
                        journal, cycle - 1, started, latest_achievement, latest_verification,
                        "max_time", "Maximum run time reached before the next cycle."
                    )

                agents = self._required_text(self.config.workspace.agents_file, "Global prompt")
                goals = self._required_text(self.config.workspace.goals_file, "Goals")
                criteria = self._required_text(self.config.workspace.criteria_file, "Pass criteria")
                expected_targets = markdown_requirements(goals)
                expected_criteria = markdown_requirements(criteria)
                handover = self._optional_text(
                    self.config.workspace.handover_file,
                    "No previous handover exists. Inspect the workspace and start from the targets.",
                )
                feedback = self._optional_text(
                    self.config.workspace.feedback_file,
                    "No independent verification feedback exists yet.",
                )

                self.output(f"[cycle {cycle}/{self.config.run.max_loops}] achievement shift")
                achievement_text, achievement_messages = self._phase(
                    f"{agents}\n\n---\n\n{ACHIEVER_SYSTEM}",
                    achiever_prompt(goals, criteria, handover, feedback, cycle),
                    self._workspace_tools(read_only=False),
                    deadline,
                    "achievement",
                )
                try:
                    latest_achievement = normalize_achievement(extract_json_object(achievement_text))
                except ValueError as exc:
                    latest_achievement = normalize_achievement(
                        {
                            "status": "blocked",
                            "summary": f"Achievement result was malformed: {exc}",
                            "todos": ["Continue the work and return the required structured result."],
                            "risks": [achievement_text[:1000]],
                        }
                    )
                journal.write_transcript("achievement", cycle, achievement_messages)
                journal.write_json(f"cycle-{cycle:03d}/achievement-result.json", latest_achievement)
                journal.write_handover(cycle, "awaiting_verification", latest_achievement, None)

                if self.clock() >= deadline:
                    return self._stop(
                        journal, cycle, started, latest_achievement, None,
                        "max_time", "Maximum run time reached before independent verification."
                    )

                # Deliberately create a new messages list and read-only tool instance. No achievement
                # transcript is passed into this independent verification context.
                self.output(f"[cycle {cycle}/{self.config.run.max_loops}] independent verification shift")
                current_handover = journal.handover_path.read_text(encoding="utf-8")
                verification_text, verification_messages = self._phase(
                    f"{agents}\n\n---\n\n{VERIFIER_SYSTEM}",
                    verifier_prompt(
                        goals,
                        criteria,
                        labeled_requirements(expected_targets, "G"),
                        labeled_requirements(expected_criteria, "C"),
                        current_handover,
                        cycle,
                    ),
                    self._workspace_tools(read_only=True),
                    deadline,
                    "verification",
                )
                try:
                    latest_verification = normalize_verification(
                        extract_json_object(verification_text), expected_targets, expected_criteria
                    )
                except ValueError as exc:
                    latest_verification = normalize_verification(
                        {
                            "passed": False,
                            "summary": f"Verification result was malformed: {exc}",
                            "criteria": [],
                            "feedback": [
                                "Run verification again and return strict JSON with evidence for every criterion."
                            ],
                        },
                        expected_targets,
                        expected_criteria,
                    )
                journal.write_transcript("verification", cycle, verification_messages)
                journal.write_json(f"cycle-{cycle:03d}/verification-result.json", latest_verification)
                journal.write_feedback(cycle, latest_verification)

                if latest_verification["passed"]:
                    journal.write_handover(
                        cycle, "complete", latest_achievement, latest_verification,
                        "All goals passed independent verification."
                    )
                    elapsed = self.clock() - started
                    journal.write_state(
                        {"status": "complete", "cycle": cycle, "elapsed_seconds": elapsed}
                    )
                    return RunOutcome(
                        True,
                        "complete",
                        cycle,
                        elapsed,
                        run_id,
                        "All goals passed independent verification.",
                    )

                journal.write_handover(
                    cycle, "verification_failed", latest_achievement, latest_verification
                )
                journal.write_state(
                    {
                        "status": "verification_failed",
                        "cycle": cycle,
                        "elapsed_seconds": self.clock() - started,
                    }
                )
                self.output(f"[cycle {cycle}] verification failed; feedback saved for next shift")

                if cycle < self.config.run.max_loops and self.config.run.delay_seconds:
                    remaining = deadline - self.clock()
                    if remaining <= self.config.run.delay_seconds:
                        return self._stop(
                            journal, cycle, started, latest_achievement, latest_verification,
                            "max_time", "Not enough run time remains for the configured inter-cycle delay."
                        )
                    self.sleeper(self.config.run.delay_seconds)

            return self._stop(
                journal, cycle, started, latest_achievement, latest_verification,
                "max_loops", f"Maximum loop count ({self.config.run.max_loops}) reached."
            )
        except KeyboardInterrupt:
            return self._stop(
                journal, cycle, started, latest_achievement, latest_verification,
                "interrupted", "Run interrupted by user."
            )
        except TimeoutError as exc:
            return self._stop(
                journal, cycle, started, latest_achievement, latest_verification,
                "max_time", str(exc)
            )
        except (ApiError, AgentRunError, ConfigError, OSError) as exc:
            journal.write_handover(
                cycle, "error", latest_achievement, latest_verification, str(exc)
            )
            journal.write_state(
                {"status": "error", "cycle": cycle, "error": str(exc),
                 "elapsed_seconds": self.clock() - started}
            )
            raise AgentRunError(str(exc)) from exc

    def _workspace_tools(self, read_only: bool) -> WorkspaceTools:
        workspace = self.config.workspace
        protected = [
            workspace.path_for(workspace.agents_file),
            workspace.path_for(workspace.goals_file),
            workspace.path_for(workspace.criteria_file),
            workspace.path_for(workspace.handover_file),
            workspace.path_for(workspace.feedback_file),
            workspace.path_for(workspace.state_dir),
        ]
        try:
            self.config.source.relative_to(workspace.root)
        except ValueError:
            pass
        else:
            protected.append(self.config.source)
        return WorkspaceTools(
            workspace.root,
            self.config.tools,
            read_only=read_only,
            protected_paths=protected,
        )

    def _stop(
        self,
        journal: RunJournal,
        cycle: int,
        started: float,
        achievement: dict[str, Any],
        verification: dict[str, Any] | None,
        status: str,
        message: str,
    ) -> RunOutcome:
        elapsed = self.clock() - started
        journal.write_handover(cycle, status, achievement, verification, message)
        journal.write_state(
            {"status": status, "cycle": cycle, "elapsed_seconds": elapsed, "message": message}
        )
        return RunOutcome(False, status, cycle, elapsed, journal.run_id, message)
