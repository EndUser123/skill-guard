#!/usr/bin/env python3
r"""
manual_invocation_tracker.py
=============================

Canonical tracker for manual skill invocations (/gto, /package, etc.).

Integrates with ExecutionRuntime to provide a structured obligation for
manually invoked skills, validated at Stop time using multiple evidence sources:
- execution-events.jsonl (canonical event log)
- breadcrumb trails (workflow step verification)
- ledger events (tool usage history)

This module provides the canonical interface for manual invocation tracking
and Stop-time evidence verification.

INVARIANT 1 (UPS creates the obligation):
  UserPromptSubmit hook calls create_manual_invocation() to register an obligation.
  This creates an ExecutionRun with contract_type=manual-invocation and stores
  structured evidence requirements.

INVARIANT 2 (Stop validates against evidence):
  Stop hook calls validate_manual_invocation() which checks:
  - ExecutionRun status (from evaluate_completion)
  - Breadcrumb trail completion (if workflow_steps declared)
  - Ledger tool events (execution evidence)
  - Returns validated/missing-evidence/warned status

INVARIANT 3 (Fail-open on infrastructure):
  All functions return safe defaults (allow/warn) on I/O failures.
  Only fail-closed on narrow, static safety violations.

Design Principles:
- Use ExecutionRuntime as canonical state store (no parallel ledgers)
- Evidence collection uses existing breadcrumb/ledger mechanisms
- Stop is the primary validation point (not PreToolUse)
- Graceful degradation after bounded retries
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Import ExecutionRuntime for canonical state management
from skill_guard.execution_runtime import ExecutionRuntime, validate_response_requirements
from skill_guard.execution_run import ExecutionRun

# Import slash command detection from existing module
from skill_guard.slash_command_observability import (
    BUILTIN_SLASH_COMMANDS,
    LIGHTWEIGHT_SLASH_COMMANDS,
    extract_slash_command,
)

# Import terminal detection
from skill_guard.utils.terminal_detection import detect_terminal_id


# =============================================================================
# ENUMS
# =============================================================================


class InvocationStatus(str, Enum):
    """Status of a manual skill invocation."""
    PENDING = "pending"  # Invoked but not yet validated
    VALIDATED = "validated"  # Evidence confirmed skill executed
    MISSING_EVIDENCE = "missing_evidence"  # Some required evidence not found
    WARNED = "warned"  # Retries exhausted, warned but allowed
    BYPASSED = "bypassed"  # User bypassed enforcement


class EvidenceCategory(str, Enum):
    """Types of evidence that can indicate skill execution."""
    TOOL_EVENTS = "tool_events"  # Tool usage in ledger
    BREADCRUMB_STEPS = "breadcrumb_steps"  # Workflow step completion
    ARTIFACTS_CREATED = "artifacts_created"  # Files written via Write/Edit
    SKILL_LOADED = "skill_loaded"  # Skill tool was called
    RESPONSE_TEXT = "response_text"  # Response contains required markers


@dataclass
class EvidenceRequirement:
    """A required piece of evidence for skill execution validation."""
    category: EvidenceCategory
    description: str
    required: bool = True
    patterns: list[str] = field(default_factory=list)  # For response_text matching


@dataclass
class ValidationResult:
    """Result of manual invocation validation."""
    status: InvocationStatus
    missing_requirements: list[str] = field(default_factory=list)
    evidence_found: dict[EvidenceCategory, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 2
    reason: str = ""


# =============================================================================
# CONFIGURATION
# =============================================================================

# Bounded retry configuration
DEFAULT_MAX_RETRIES = 2
WARN_ON_RETRY_EXHAUSTED = True

# Evidence collection paths (centralized for easy modification)
HOOKS_LIB_DIR = Path(r"P:\.claude\hooks\__lib")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _detect_terminal_id() -> str:
    """Get terminal ID with fallback."""
    try:
        tid = detect_terminal_id()
        if tid:
            return tid
    except Exception:
        pass
    return os.environ.get("CLAUDE_TERMINAL_ID", "unknown")


def _load_ledger_skill_events(terminal_id: str) -> list[dict]:
    """Load skill-related events from the hook ledger.

    Fail-open: returns empty list on any error.
    """
    if not terminal_id:
        return []

    try:
        if HOOKS_LIB_DIR.exists() and str(HOOKS_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_LIB_DIR))

        # Import _load_db_skill_events from hook_ledger
        from hook_ledger import _load_db_skill_events

        return _load_db_skill_events(str(terminal_id))
    except Exception:
        return []


def _get_active_turn_id(terminal_id: str) -> str:
    """Get the active turn ID from the ledger.

    Fail-open: returns empty string on any error.
    """
    if not terminal_id:
        return ""

    try:
        if HOOKS_LIB_DIR.exists() and str(HOOKS_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_LIB_DIR))

        import hook_ledger

        return hook_ledger.get_active_turn(terminal_id) or ""
    except Exception:
        return ""


def _is_ignorable_command(command: str) -> bool:
    """Check if command should not trigger manual invocation tracking.

    Built-in and lightweight commands are tracked by the system but don't
    require manual invocation enforcement.
    """
    cmd_lower = command.lower()
    return (
        cmd_lower in BUILTIN_SLASH_COMMANDS
        or cmd_lower in LIGHTWEIGHT_SLASH_COMMANDS
        or cmd_lower in {"help", "discover", "ask", "search"}
    )


# =============================================================================
# MAIN INTERFACE
# =============================================================================


def create_manual_invocation(
    skill_name: str,
    session_id: str,
    prompt: str,
    turn_id: str | None = None,
) -> ExecutionRun | None:
    """Create a structured obligation for a manually invoked skill.

    Called by UserPromptSubmit when detecting /skill-name invocation.

    Creates an ExecutionRun with:
    - contract_type: "manual-invocation" (special marker)
    - Evidence requirements derived from skill frontmatter
    - Terminal-scoped state (via ArtifactsExecutionStore)

    Fail-open: returns None on any error, allowing the skill to execute
    without blocking on infrastructure issues.

    Args:
        skill_name: Name of the skill (e.g., "gto", "package")
        session_id: Claude session ID
        prompt: Full user prompt for context
        turn_id: Optional turn ID for this invocation

    Returns:
        ExecutionRun if created successfully, None on failure (fail-open)
    """
    # Skip ignorable commands early
    if _is_ignorable_command(skill_name):
        return None

    terminal_id = _detect_terminal_id()
    if not terminal_id:
        return None

    try:
        runtime = ExecutionRuntime()

        # Build evidence requirements from skill frontmatter
        evidence_reqs = _build_evidence_requirements(skill_name)

        # Create the run with manual-invocation contract type
        run = runtime.create_run(
            skill_name=skill_name,
            contract_type="manual-invocation",
            session_id=session_id,
            allowed_tools=_get_allowed_tools_for_skill(skill_name),
            blocked_tools=_get_blocked_tools_for_skill(skill_name),
            response_requirements={
                "required_markers": evidence_reqs.get("required_markers", []),
                "prohibited_claims": [],
                "must_use_skill": False,
                "evidence_bound": True,
            },
        )

        # Store turn_id if provided
        if turn_id:
            run.turn_id = turn_id
            runtime.store.save_run(run)

        # Store evidence requirements in run metadata
        if hasattr(run, "metadata"):
            run.metadata["evidence_requirements"] = evidence_reqs
            runtime.store.save_run(run)

        return run

    except Exception:
        # Fail-open: don't block on infrastructure issues
        return None


def validate_manual_invocation(
    skill_name: str,
    session_id: str,
    transcript_path: str = "",
    response_text: str | None = None,
) -> ValidationResult:
    """Validate that a manually invoked skill was properly executed.

    Called by Stop hook to validate completion of manual invocations.

    Checks:
    1. ExecutionRun exists and is active
    2. Skill tool was called (skill_loaded event in ledger)
    3. Required evidence categories are satisfied
    4. Retry budget is respected (warn after N failures)

    Returns ValidationResult with status and missing requirements.

    Fail-open: returns status=WARNED on infrastructure failures,
    allowing the user to continue with a warning message.

    Args:
        skill_name: Name of the skill being validated
        session_id: Session ID for this invocation
        transcript_path: Optional path to transcript for response extraction
        response_text: Optional response text for structured-output checks

    Returns:
        ValidationResult with validation status and details
    """
    terminal_id = _detect_terminal_id()
    result = ValidationResult(
        status=InvocationStatus.VALIDATED,
        retry_count=0,
        max_retries=DEFAULT_MAX_RETRIES,
    )

    if not terminal_id:
        # No terminal ID - fail-open with warning
        result.status = InvocationStatus.WARNED
        result.reason = "Could not determine terminal ID for validation"
        return result

    try:
        runtime = ExecutionRuntime()
        run = runtime.load_active_run()

        # No active run or run is for a different skill
        if run is None or run.skill_name.lower() != skill_name.lower():
            result.status = InvocationStatus.WARNED
            result.reason = f"No active invocation found for /{skill_name}"
            return result

        # Check retry budget
        retry_count = _get_retry_count(terminal_id, run.run_id)
        result.retry_count = retry_count

        # Collect evidence from all sources
        evidence = _collect_evidence(
            skill_name=skill_name,
            terminal_id=terminal_id,
            turn_id=run.turn_id,
            run=run,
        )
        result.evidence_found = evidence

        # Evaluate evidence against requirements
        missing = _evaluate_evidence(evidence, run)
        result.missing_requirements = missing

        if not missing:
            # All evidence satisfied - validate the run
            runtime.finalize_run(run, "complete")
            result.status = InvocationStatus.VALIDATED
            _clear_retry_count(terminal_id, run.run_id)
            return result

        # Evidence missing - check retry budget
        if retry_count < result.max_retries:
            # Still have retries - block with actionable reason
            result.status = InvocationStatus.MISSING_EVIDENCE
            result.reason = _build_missing_evidence_reason(skill_name, missing, retry_count + 1)
            _increment_retry_count(terminal_id, run.run_id)
            return result

        # Retries exhausted - warn and allow
        result.status = InvocationStatus.WARNED
        result.reason = _build_retry_exhausted_warning(skill_name, missing)
        runtime.finalize_run(run, "warned")  # Mark as warned, not failed

    except Exception as e:
        # Infrastructure failure - fail-open with warning
        result.status = InvocationStatus.WARNED
        result.reason = f"Validation error: {str(e)[:100]}"

    return result


# =============================================================================
# EVIDENCE COLLECTION
# =============================================================================


def _build_evidence_requirements(skill_name: str) -> dict[str, Any]:
    """Build evidence requirements from skill frontmatter.

    Reads the skill's SKILL.md and extracts:
    - required_markers (for response text)
    - required_phase_artifacts (for artifact-based evidence)
    - workflow_steps (for breadcrumb tracking)

    Fail-open: returns empty dict on any error.
    """
    requirements: dict[str, Any] = {}

    try:
        from skill_guard._skill_frontmatter_loader import _load_skill_frontmatter

        frontmatter = _load_skill_frontmatter(skill_name)
        if not frontmatter:
            return requirements

        requirements = {
            "required_markers": frontmatter.get("required_markers", []),
            "required_phase_artifacts": frontmatter.get("required_phase_artifacts", []),
            "workflow_steps": frontmatter.get("workflow_steps", []),
            "allowed_first_tools": frontmatter.get("allowed_first_tools", []),
        }

    except Exception:
        pass  # Fail-open

    return requirements


def _get_allowed_tools_for_skill(skill_name: str) -> list[str]:
    """Get allowed tools for a skill from frontmatter.

    Returns empty list if no restrictions declared.
    """
    try:
        from skill_guard._skill_frontmatter_loader import _load_skill_frontmatter

        frontmatter = _load_skill_frontmatter(skill_name)
        if frontmatter:
            return frontmatter.get("allowed_first_tools", [])
    except Exception:
        pass
    return []


def _get_blocked_tools_for_skill(skill_name: str) -> list[str]:
    """Get blocked tools for a skill.

    Currently returns empty list - explicit blocking via frontmatter
    could be added in the future.
    """
    return []


def _collect_evidence(
    skill_name: str,
    terminal_id: str,
    turn_id: str | None,
    run: ExecutionRun,
) -> dict[EvidenceCategory, Any]:
    """Collect evidence from all available sources.

    Sources:
    1. Ledger events (skill_loaded, tool usage)
    2. Breadcrumb trail (workflow steps)
    3. Execution events (execution-events.jsonl)
    4. Artifacts (completed_artifacts in run)

    Returns dict mapping EvidenceCategory to evidence data.
    """
    evidence: dict[EvidenceCategory, Any] = {
        EvidenceCategory.TOOL_EVENTS: [],
        EvidenceCategory.BREADCRUMB_STEPS: [],
        EvidenceCategory.ARTIFACTS_CREATED: run.completed_artifacts,
        EvidenceCategory.SKILL_LOADED: False,
        EvidenceCategory.RESPONSE_TEXT: "",
    }

    # 1. Check ledger for skill_loaded event
    skill_events = _load_ledger_skill_events(terminal_id)
    for event in skill_events:
        payload = event.get("payload", {})

        # Check for skill_loaded event matching this skill
        if (
            event.get("event_type") == "skill_loaded"
            and payload.get("skill", "").lower() == skill_name.lower()
        ):
            evidence[EvidenceCategory.SKILL_LOADED] = True

        # Collect tool usage events
        if event.get("event_type") == "skill_tool_used":
            evidence[EvidenceCategory.TOOL_EVENTS].append(payload)

    # 2. Collect breadcrumb trail
    try:
        from skill_guard.breadcrumb.tracker import get_breadcrumb_trail

        trail = get_breadcrumb_trail(skill_name)
        if trail:
            evidence[EvidenceCategory.BREADCRUMB_STEPS] = trail.get("completed_steps", [])
    except Exception:
        pass  # Breadcrumb system may not be available

    # 3. Collect execution events
    try:
        execution_events = run.store.replay_events()
        evidence[EvidenceCategory.TOOL_EVENTS].extend(
            [e.to_jsonable() for e in execution_events]
        )
    except Exception:
        pass

    return evidence


def _evaluate_evidence(
    evidence: dict[EvidenceCategory, Any],
    run: ExecutionRun,
) -> list[str]:
    """Evaluate collected evidence against requirements.

    Returns list of missing requirement descriptions.

    Checks:
    - Skill tool was called (SKILL_LOADED)
    - Required artifacts were created
    - Breadcrumb steps completed (if workflow_steps declared)
    """
    missing: list[str] = []

    # Check if skill was loaded
    if not evidence.get(EvidenceCategory.SKILL_LOADED, False):
        missing.append("Skill tool was not called")

    # Check required artifacts
    required_artifacts = run.required_artifacts
    if required_artifacts:
        completed = evidence.get(EvidenceCategory.ARTIFACTS_CREATED, [])
        missing_artifacts = [a for a in required_artifacts if a not in completed]
        if missing_artifacts:
            missing.append(f"Missing required artifacts: {', '.join(missing_artifacts)}")

    # Check breadcrumb steps if workflow_steps declared
    breadcrumb_steps = evidence.get(EvidenceCategory.BREADCRUMB_STEPS, [])
    if breadcrumb_steps and run.response_requirements.get("workflow_steps"):
        # All steps should be complete
        required_steps = run.response_requirements["workflow_steps"]
        missing_steps = [s for s in required_steps if s not in breadcrumb_steps]
        if missing_steps:
            missing.append(f"Missing workflow steps: {', '.join(missing_steps)}")

    return missing


# =============================================================================
# RETRY MANAGEMENT
# =============================================================================


def _get_retry_state_path(terminal_id: str, run_id: str) -> Path:
    """Get the path to the retry state file for this run."""
    # Use hooks/state directory to avoid conflicts with main state
    hooks_dir = Path(r"P:\.claude\hooks\state")
    safe_terminal = terminal_id.replace("/", "-").replace("\\", "-").replace(":", "-")
    return hooks_dir / f"manual_invocation_retry_{safe_terminal}_{run_id}.json"


def _get_retry_count(terminal_id: str, run_id: str) -> int:
    """Get current retry count for a run.

    Returns 0 if no retry state exists.
    """
    state_path = _get_retry_state_path(terminal_id, run_id)
    if not state_path.exists():
        return 0

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data.get("retry_count", 0)
    except Exception:
        return 0


def _increment_retry_count(terminal_id: str, run_id: str) -> None:
    """Increment retry count for a run."""
    state_path = _get_retry_state_path(terminal_id, run_id)
    retry_count = _get_retry_count(terminal_id, run_id) + 1

    state = {
        "run_id": run_id,
        "retry_count": retry_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass  # Fail-open - retry state is advisory


def _clear_retry_count(terminal_id: str, run_id: str) -> None:
    """Clear retry state for a run."""
    state_path = _get_retry_state_path(terminal_id, run_id)
    try:
        state_path.unlink(missing_ok=True)
    except Exception:
        pass


# =============================================================================
# REASON BUILDERS
# =============================================================================


def _build_missing_evidence_reason(
    skill_name: str,
    missing: list[str],
    retry_num: int,
) -> str:
    """Build a user-facing reason for missing evidence.

    Includes specific missing requirements and retry count.
    """
    lines = [
        f"MANUAL SKILL INVOCATION NOT COMPLETE: /{skill_name}",
        "",
        f"This is attempt {retry_num} of {DEFAULT_MAX_RETRIES + 1}.",
        "",
        "The skill was invoked but the required evidence was not found:",
    ]

    for item in missing:
        lines.append(f"  • {item}")

    lines.extend([
        "",
        "Please execute the skill workflow completely before stopping.",
    ])

    return "\n".join(lines)


def _build_retry_exhausted_warning(
    skill_name: str,
    missing: list[str],
) -> str:
    """Build a warning when retry budget is exhausted.

    Allows the user to proceed but emits a warning about incomplete execution.
    """
    lines = [
        f"⚠️ SKILL INVOCATION WARNING: /{skill_name}",
        "",
        f"Retries exhausted ({DEFAULT_MAX_RETRIES} attempts).",
        "Allowing session to continue, but the skill workflow may be incomplete.",
        "",
        "Missing evidence:",
    ]

    for item in missing[:5]:  # Limit to 5 items
        lines.append(f"  • {item}")

    if len(missing) > 5:
        lines.append(f"  • ... and {len(missing) - 5} more")

    return "\n".join(lines)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "InvocationStatus",
    "EvidenceCategory",
    "EvidenceRequirement",
    "ValidationResult",
    "create_manual_invocation",
    "validate_manual_invocation",
]