"""Durable handover, feedback, state, and transcript files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import WorkspaceConfig


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bullets(items: list[Any], empty: str = "None recorded.") -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "\n".join(f"- {item}" for item in cleaned) if cleaned else f"- {empty}"


@dataclass
class RunJournal:
    workspace: WorkspaceConfig
    run_id: str

    def __post_init__(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.run_root.mkdir(parents=True, exist_ok=True)

    @property
    def state_root(self) -> Path:
        return self.workspace.path_for(self.workspace.state_dir)

    @property
    def run_root(self) -> Path:
        return self.state_root / "runs" / self.run_id

    @property
    def handover_path(self) -> Path:
        return self.workspace.path_for(self.workspace.handover_file)

    @property
    def feedback_path(self) -> Path:
        return self.workspace.path_for(self.workspace.feedback_file)

    def read_or_default(self, path: Path, default: str) -> str:
        if not path.exists():
            return default
        return path.read_text(encoding="utf-8")

    def write_json(self, relative_path: str, data: Any) -> None:
        path = self.run_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_transcript(self, phase: str, cycle: int, messages: list[dict[str, Any]]) -> None:
        self.write_json(f"cycle-{cycle:03d}/{phase}-transcript.json", messages)

    def write_state(self, data: dict[str, Any]) -> None:
        enriched = {**data, "updated_at": utc_now(), "run_id": self.run_id}
        self.write_json("state.json", enriched)
        (self.state_root / "latest-state.json").write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def write_handover(
        self,
        cycle: int,
        status: str,
        achievement: dict[str, Any],
        verification: dict[str, Any] | None,
        stop_reason: str | None = None,
    ) -> None:
        verification = verification or {}
        targets = verification.get("targets", [])
        criteria = verification.get("criteria", [])
        target_lines = []
        for item in targets if isinstance(targets, list) else []:
            if not isinstance(item, dict):
                continue
            mark = "PASS" if item.get("passed") is True else "FAIL"
            item_id = str(item.get("id", "G?")).strip()
            target = str(item.get("target", "Unnamed target")).strip()
            evidence = str(item.get("evidence", "No evidence recorded")).strip()
            feedback = str(item.get("feedback", "")).strip()
            line = f"- [{mark}] {item_id}: {target} — Evidence: {evidence}"
            if feedback:
                line += f" — Correction: {feedback}"
            target_lines.append(line)
        criteria_lines = []
        for item in criteria if isinstance(criteria, list) else []:
            if not isinstance(item, dict):
                continue
            mark = "PASS" if item.get("passed") is True else "FAIL"
            item_id = str(item.get("id", "C?")).strip()
            criterion = str(item.get("criterion", "Unnamed criterion")).strip()
            evidence = str(item.get("evidence", "No evidence recorded")).strip()
            feedback = str(item.get("feedback", "")).strip()
            line = f"- [{mark}] {item_id}: {criterion} — Evidence: {evidence}"
            if feedback:
                line += f" — Correction: {feedback}"
            criteria_lines.append(line)

        content = f"""# Agent Handover

This file is maintained by the orchestrator. It is the durable, detailed shift handover for the next
fresh achievement context.

## Current status

- Run ID: `{self.run_id}`
- Updated: `{utc_now()}`
- Completed cycles: {cycle}
- Status: **{status}**
- Stop reason: {stop_reason or "Not stopped; continue from the items below."}

## What was done in the latest achievement shift

{_bullets(achievement.get("completed", []))}

## Shift summary

{str(achievement.get("summary", "No summary was returned.")).strip()}

## Tests and checks already run

{_bullets(achievement.get("tests", []))}

## TODOs for the next achievement shift

{_bullets(achievement.get("todos", []), "No achiever TODOs recorded; still inspect verification feedback.")}

## Risks, uncertainties, and blockers

{_bullets(achievement.get("risks", []))}

## Independent verification result

- Overall pass: {verification.get("passed", "Not run")}
- Verdict: {str(verification.get("summary", "Verification has not run for this shift.")).strip()}

### Criterion-by-criterion evidence

{chr(10).join(criteria_lines) if criteria_lines else "- No criterion evidence recorded yet."}

### Target-by-target evidence

{chr(10).join(target_lines) if target_lines else "- No target evidence recorded yet."}

### Required corrections from verifier

{_bullets(verification.get("feedback", []), "No verifier corrections recorded.")}

## Next-shift operating instructions

- Re-read `AGENTS.md`, `GOALS.md`, and `PASS_CRITERIA.md`; they are authoritative and may have changed.
- Inspect the workspace instead of assuming this handover is correct.
- Address failed verification items before optional improvements.
- Run relevant checks and report exact evidence, remaining TODOs, and risks for the following shift.
"""
        self.handover_path.parent.mkdir(parents=True, exist_ok=True)
        self.handover_path.write_text(content, encoding="utf-8")

    def write_feedback(self, cycle: int, verification: dict[str, Any]) -> None:
        targets = verification.get("targets", [])
        criteria = verification.get("criteria", [])
        failed_lines = []
        for item in targets if isinstance(targets, list) else []:
            if isinstance(item, dict) and item.get("passed") is not True:
                failed_lines.append(
                    "- **{} (target)**: {} Evidence: {}".format(
                        str(item.get("id", "G?")).strip(),
                        str(item.get("feedback", "No correction supplied.")).strip(),
                        str(item.get("evidence", "No evidence supplied.")).strip(),
                    )
                )
        for item in criteria if isinstance(criteria, list) else []:
            if isinstance(item, dict) and item.get("passed") is not True:
                failed_lines.append(
                    "- **{} (criterion)**: {} Evidence: {}".format(
                        str(item.get("id", "C?")).strip(),
                        str(item.get("feedback", "No correction supplied.")).strip(),
                        str(item.get("evidence", "No evidence supplied.")).strip(),
                    )
                )
        content = f"""# Verification Feedback

- Run ID: `{self.run_id}`
- Cycle: {cycle}
- Updated: `{utc_now()}`
- Overall passed: **{verification.get("passed", False)}**

## Verdict

{str(verification.get("summary", "No summary returned.")).strip()}

## Failed criteria and evidence

{chr(10).join(failed_lines) if failed_lines else "- None. All reported criteria passed."}

## Prioritized actions for the next achievement shift

{_bullets(verification.get("feedback", []), "No corrective action required.")}
"""
        self.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        self.feedback_path.write_text(content, encoding="utf-8")
