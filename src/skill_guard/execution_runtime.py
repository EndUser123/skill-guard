"""
execution_runtime.py
==================

ExecutionRuntime facade wrapping an ExecutionStore.

Provides:
- create_run(), load_active_run()
- record_tool_use() — emits tool_allowed/tool_blocked, transitions phase, sets FAILED
- record_artifact_created() — emits artifact_created, updates completed_artifacts
- evaluate_completion() — short-circuits on FAILED, applies contract rules
- finalize_run() — emits run_ended event and clears state

validate_response_requirements() is a module-level helper (no state needed).
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from .execution_run import ExecutionEvent, ExecutionRun, RunStatus
from .execution_store import ArtifactsExecutionStore, ExecutionStore


# ---------------------------------------------------------------------------
# Public helpers (no state needed)
# ---------------------------------------------------------------------------

@dataclass
class ResponseCheckResult:
    ok: bool
    missing: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def validate_response_requirements(response_text: str, requirements: dict) -> ResponseCheckResult:
    """
    Check structured-output response against requirements.

    - sections: all listed keywords must appear in response_text (case-insensitive)
    - prohibited_claims: none of these phrases may appear (case-insensitive)
    """
    missing: list[str] = []
    violations: list[str] = []

    for section in requirements.get("sections", []):
        if section.lower() not in response_text.lower():
            missing.append(f"section:{section}")

    for phrase in requirements.get("prohibited_claims", []):
        if phrase.lower() in response_text.lower():
            violations.append(f"prohibited:{phrase}")

    return ResponseCheckResult(ok=not missing and not violations, missing=missing, violations=violations)


# ---------------------------------------------------------------------------
# Runtime facade
# ---------------------------------------------------------------------------

class ExecutionRuntime:
    """
    Facade for execution contract enforcement.

    PreToolUse calls record_tool_use() to check allow/block and record events.
    PostToolUse calls record_artifact_created() to update artifact completion.
    Stop calls evaluate_completion() + finalize_run() to determine status.
    """

    def __init__(self, store: ExecutionStore | None = None):
        if store is None:
            terminal_id = self._detect_terminal_id()
            store = ArtifactsExecutionStore(terminal_id)
        self.store = store

    def _detect_terminal_id(self) -> str:
        try:
            from .utils.terminal_detection import detect_terminal_id
            tid = detect_terminal_id()
            if tid:
                return tid
        except ImportError:
            pass
        return os.environ.get("CLAUDE_TERMINAL_ID", "unknown")

    # -------------------------------------------------------------------------
    # Run lifecycle
    # -------------------------------------------------------------------------

    def create_run(
        self,
        skill_name: str,
        contract_type: str,
        session_id: str,
        required_artifacts: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        response_requirements: dict[str, Any] | None = None,
    ) -> ExecutionRun:
        """Create a new run and persist it to the store."""
        run = ExecutionRun.new(
            skill_name=skill_name,
            contract_type=contract_type,  # type: ignore[arg-type]
            terminal_id=self.store.console_dir().name,
            session_id=session_id,
            required_artifacts=required_artifacts or [],
            allowed_tools=allowed_tools or [],
            blocked_tools=blocked_tools or [],
            response_requirements=response_requirements or {},
        )
        self.store.save_run(run)
        self.store.append_event(ExecutionEvent(event_type="run_created", skill=skill_name))
        return run

    def load_active_run(self) -> ExecutionRun | None:
        return self.store.load_active_run()

    # -------------------------------------------------------------------------
    # Tool events (PreToolUse owns these)
    # -------------------------------------------------------------------------

    def record_tool_use(
        self,
        run: ExecutionRun,
        tool_name: str,
        allowed: bool,
        reason: str | None = None,
    ) -> None:
        """
        Record a tool use event.

        - Emits tool_allowed or tool_blocked to the event log.
        - If blocked: sets run.status = FAILED immediately.
        - Transitions phase: pending→loaded (on first allowed tool check),
          loaded→executing (on first allowed tool call).
        - blocked_tools violation sets FAILED and does not transition phase.
        """
        if allowed:
            event_type = "tool_allowed"
            if run.phase == "pending":
                run.phase = "loaded"
            elif run.phase == "loaded":
                run.phase = "executing"
        else:
            event_type = "tool_blocked"
            run.status = RunStatus.FAILED

        self.store.append_event(ExecutionEvent(
            event_type=event_type,
            tool=tool_name,
            reason=reason,
        ))
        self.store.save_run(run)

    # -------------------------------------------------------------------------
    # Artifact events (PostToolUse owns these)
    # -------------------------------------------------------------------------

    def record_artifact_created(self, run: ExecutionRun, path: str) -> None:
        """
        Record an artifact created event.

        - Emits artifact_created to the event log.
        - Adds path to completed_artifacts; removes from missing_requirements.
        - Does NOT touch phase, status, or tool events (PreToolUse owns those).
        """
        if path not in run.completed_artifacts:
            run.completed_artifacts.append(path)
        if path in run.missing_requirements:
            run.missing_requirements.remove(path)
        self.store.append_event(ExecutionEvent(event_type="artifact_created", path=path))
        self.store.save_run(run)

    # -------------------------------------------------------------------------
    # Completion evaluation
    # -------------------------------------------------------------------------

    def evaluate_completion(self, run: ExecutionRun, response_text: str | None = None) -> str:
        """
        Determine run status: ACTIVE | COMPLETE | FAILED.

        Rules:
        - FAILED short-circuits: always return FAILED if run.status is FAILED.
        - workflow-execution: COMPLETE when all required_artifacts done and no missing_requirements.
        - structured-output: COMPLETE when validate_response_requirements(...).ok == True.
          CONTINUE when requirements unmet; FAILED short-circuits above.
        - hybrid: requires both workflow artifacts and response validation.
        """
        if run.status == RunStatus.FAILED:
            return RunStatus.FAILED

        if run.contract_type == "workflow-execution":
            all_done = all(a in run.completed_artifacts for a in run.required_artifacts)
            return RunStatus.COMPLETE if (all_done and not run.missing_requirements) else RunStatus.ACTIVE

        if run.contract_type == "structured-output":
            if response_text is None:
                return RunStatus.ACTIVE
            result = validate_response_requirements(response_text, run.response_requirements)
            run.missing_requirements = result.missing + result.violations
            self.store.save_run(run)
            return RunStatus.COMPLETE if result.ok else RunStatus.ACTIVE

        if run.contract_type == "hybrid":
            all_done = all(a in run.completed_artifacts for a in run.required_artifacts)
            if response_text is not None:
                result = validate_response_requirements(response_text, run.response_requirements)
                run.missing_requirements = [
                    *[r for r in run.missing_requirements if r not in result.missing + result.violations],
                    *result.missing,
                    *result.violations,
                ]
                self.store.save_run(run)
            return RunStatus.COMPLETE if (all_done and not run.missing_requirements) else RunStatus.ACTIVE

        return RunStatus.ACTIVE

    # -------------------------------------------------------------------------
    # Finalization
    # -------------------------------------------------------------------------

    def finalize_run(self, run: ExecutionRun, status: str) -> None:
        """End the run: emit run_ended event, persist final state, clear active state."""
        run.status = status
        self.store.save_run(run)
        self.store.end_run(run, status)