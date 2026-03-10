#!/usr/bin/env python3
"""
Breadcrumb Trail Tracker
========================

Workflow step verification system for skill execution.

This module implements the breadcrumb trail pattern:
1. Skills declare workflow_steps in SKILL.md frontmatter
2. Skill hooks call set_breadcrumb() as steps complete
3. Global hooks verify breadcrumb trail completion
4. Block or advise when trail is incomplete

State files are terminal-scoped for multi-terminal safety.
Automatic cleanup on SessionEnd and PreCompact prevents filesystem litter.

v2.0 CHANGES:
- Terminal-scoped only (no session_id - session_id changes during compaction)
- Automatic cleanup on SessionEnd (all trails for this terminal)
- Automatic cleanup on PreCompact (stale trails)
- Age-based cleanup for orphaned trails (>2 hours old)
- No TTL - cleanup based on lifecycle events, not time
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# Import terminal detection from skill_guard utilities
from skill_guard.utils.terminal_detection import detect_terminal_id

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")
# Maximum age for breadcrumb trails (2 hours)
MAX_TRAIL_AGE_SECONDS = 7200

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

def _get_breadcrumb_dir() -> Path:
    """Get the breadcrumb state directory for this terminal."""
    terminal_id = detect_terminal_id()
    breadcrumb_dir = STATE_DIR / f"breadcrumbs_{terminal_id}"
    breadcrumb_dir.mkdir(parents=True, exist_ok=True)
    return breadcrumb_dir


def _get_breadcrumb_file(skill_name: str) -> Path:
    """Get the breadcrumb trail file for a skill."""
    skill_lower = skill_name.lower().replace("/", "_").replace(" ", "_")
    return _get_breadcrumb_dir() / f"breadcrumb_{skill_lower}.json"


def _load_workflow_steps(skill_name: str) -> list[str]:
    """Load workflow_steps from a skill's SKILL.md frontmatter.

    Args:
        skill_name: Skill name (without slash)

    Returns:
        List of workflow step names (empty if not declared)
    """
    steps: list[str] = []
    skill_dir = Path("P:/.claude/skills") / skill_name.lower()
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return steps

    try:
        import yaml  # noqa: PLC0415
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return steps
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return steps
        wf_steps = fm_data.get("workflow_steps", [])
        if isinstance(wf_steps, list):
            steps = [str(s) for s in wf_steps]
    except Exception:
        pass

    return steps


def initialize_breadcrumb_trail(skill_name: str) -> None:
    """Initialize breadcrumb trail for a skill.

    Called when a skill is invoked. Loads workflow_steps from frontmatter
    and creates breadcrumb state file with all steps as "pending".

    Args:
        skill_name: Name of the skill being invoked
    """
    skill_lower = skill_name.lower()

    # Load workflow steps from frontmatter
    workflow_steps = _load_workflow_steps(skill_lower)

    # If no workflow steps declared, don't track
    if not workflow_steps:
        return

    # Initialize breadcrumb trail (terminal-scoped only, not session-scoped)
    # CRITICAL: Only use terminal_id for multi-terminal safety
    # Session ID is global across terminals and changes during compaction
    trail = {
        "skill": skill_lower,
        "terminal_id": detect_terminal_id(),
        "initialized_at": time.time(),
        "workflow_steps": workflow_steps,
        "completed_steps": [],
        "current_step": None,
        "last_updated": time.time(),
    }

    # Write breadcrumb file
    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    breadcrumb_file.write_text(json.dumps(trail, indent=2))


def set_breadcrumb(skill_name: str, step_name: str) -> None:
    """Mark a workflow step as completed.

    Called by skill hooks as they complete workflow steps.

    Args:
        skill_name: Name of the skill
        step_name: Name of the completed step (must match workflow_steps)
    """
    skill_lower = skill_name.lower()

    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    if not breadcrumb_file.exists():
        # Trail not initialized, initialize first
        initialize_breadcrumb_trail(skill_lower)
        if not breadcrumb_file.exists():
            return  # No workflow steps declared

    try:
        trail = json.loads(breadcrumb_file.read_text())

        # Validate step is in workflow_steps
        if step_name not in trail.get("workflow_steps", []):
            # Invalid step name, ignore
            return

        # Add to completed_steps if not already there
        completed = trail.get("completed_steps", [])
        if step_name not in completed:
            completed.append(step_name)
            trail["completed_steps"] = completed
            trail["current_step"] = step_name
            trail["last_updated"] = time.time()

            # Write updated trail
            breadcrumb_file.write_text(json.dumps(trail, indent=2))

    except (json.JSONDecodeError, OSError):
        pass


def get_breadcrumb_trail(skill_name: str) -> dict[str, Any] | None:
    """Get current breadcrumb trail for a skill.

    Verifies session isolation to prevent cross-terminal contamination.

    Args:
        skill_name: Name of the skill

    Returns:
        Trail dict or None if no trail exists or session mismatch
    """
    skill_lower = skill_name.lower()
    breadcrumb_file = _get_breadcrumb_file(skill_lower)

    if not breadcrumb_file.exists():
        return None

    try:
        trail = json.loads(breadcrumb_file.read_text())

        # Verify session isolation (multi-terminal safety)
        if not verify_session_isolation(trail):
            # Remove stale trail from different session/terminal
            breadcrumb_file.unlink(missing_ok=True)
            return None

        return trail

    except (json.JSONDecodeError, OSError):
        return None


def verify_breadcrumb_trail(skill_name: str) -> tuple[bool, str]:
    """Verify that all workflow steps have been completed.

    Args:
        skill_name: Name of the skill

    Returns:
        (is_complete, message) tuple
    """
    trail = get_breadcrumb_trail(skill_name)

    if not trail:
        # No breadcrumb trail means no workflow steps declared
        return True, "No workflow steps declared"

    workflow_steps = trail.get("workflow_steps", [])
    completed_steps = trail.get("completed_steps", [])

    if not workflow_steps:
        return True, "No workflow steps declared"

    # Check for missing steps
    missing_steps = [step for step in workflow_steps if step not in completed_steps]

    if missing_steps:
        return False, f"Missing workflow steps: {', '.join(missing_steps)}"

    return True, "All workflow steps completed"


def clear_breadcrumb_trail(skill_name: str) -> None:
    """Clear breadcrumb trail for a skill.

    Called when skill execution is complete.

    Args:
        skill_name: Name of the skill
    """
    skill_lower = skill_name.lower()
    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    breadcrumb_file.unlink(missing_ok=True)


def clear_all_breadcrumb_trails() -> None:
    """Clear all breadcrumb trails for this terminal.

    Useful for cleanup or state reset.
    """
    breadcrumb_dir = _get_breadcrumb_dir()
    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        file.unlink(missing_ok=True)


# =============================================================================
# CLEANUP PROTOCOL
# =============================================================================

def cleanup_session_breadcrumbs() -> int:
    """Clean up all breadcrumb trails for this terminal (SessionEnd hook).

    Called by SessionEnd hook to clean up trails when session terminates.
    This prevents stale breadcrumb trails from littering the filesystem.

    Returns:
        Number of trails cleaned up
    """
    current_terminal_id = detect_terminal_id()
    breadcrumb_dir = _get_breadcrumb_dir()

    if not breadcrumb_dir.exists():
        return 0

    cleaned_count = 0
    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())

            # Only clean up trails from this terminal (not session-scoped)
            trail_terminal = trail.get("terminal_id")

            if trail_terminal == current_terminal_id:
                file.unlink(missing_ok=True)
                cleaned_count += 1

        except (json.JSONDecodeError, OSError):
            # Cleanup invalid files
            file.unlink(missing_ok=True)
            cleaned_count += 1

    return cleaned_count


def cleanup_stale_breadcrumbs() -> int:
    """Clean up stale breadcrumb trails (PreCompact hook).

    Removes breadcrumb trails that are older than MAX_TRAIL_AGE_SECONDS.
    This prevents orphaned trails from accumulating over time.

    Called by PreCompact hook before session compaction occurs.

    Returns:
        Number of stale trails cleaned up
    """
    current_time = time.time()
    current_terminal_id = detect_terminal_id()
    breadcrumb_dir = _get_breadcrumb_dir()

    if not breadcrumb_dir.exists():
        return 0

    cleaned_count = 0
    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())

            # Check trail age
            initialized_at = trail.get("initialized_at", current_time)
            trail_age = current_time - initialized_at

            # Clean up stale trails
            if trail_age > MAX_TRAIL_AGE_SECONDS:
                file.unlink(missing_ok=True)
                cleaned_count += 1
                continue

            # Clean up trails from other terminals (cross-terminal contamination)
            trail_terminal = trail.get("terminal_id")
            if trail_terminal != current_terminal_id:
                file.unlink(missing_ok=True)
                cleaned_count += 1

        except (json.JSONDecodeError, OSError):
            # Cleanup invalid files
            file.unlink(missing_ok=True)
            cleaned_count += 1

    return cleaned_count


def verify_session_isolation(trail: dict[str, Any]) -> bool:
    """Verify that a breadcrumb trail belongs to this terminal.

    CRITICAL: Only checks terminal_id, not session_id.
    Session ID is global across terminals and changes during compaction.

    Args:
        trail: Trail dict to verify

    Returns:
        True if trail belongs to this terminal, False otherwise
    """
    current_terminal_id = detect_terminal_id()
    trail_terminal = trail.get("terminal_id")

    # Only check terminal_id (session_id changes during compaction)
    return trail_terminal == current_terminal_id


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_active_breadcrumb_trails() -> list[dict[str, Any]]:
    """Get all active breadcrumb trails for this terminal.

    Returns:
        List of trail dicts
    """
    breadcrumb_dir = _get_breadcrumb_dir()
    trails = []

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())
            trails.append(trail)
        except (json.JSONDecodeError, OSError):
            pass

    return trails


def format_breadcrumb_status(trail: dict[str, Any]) -> str:
    """Format breadcrumb trail for display.

    Args:
        trail: Trail dict from get_breadcrumb_trail()

    Returns:
        Formatted status string
    """
    skill = trail.get("skill", "unknown")
    workflow_steps = trail.get("workflow_steps", [])
    completed_steps = trail.get("completed_steps", [])

    status = f"Skill: {skill}\n"
    status += f"Workflow: {len(completed_steps)}/{len(workflow_steps)} steps complete\n"

    if completed_steps:
        status += f"Completed: {', '.join(completed_steps)}\n"

    missing = [step for step in workflow_steps if step not in completed_steps]
    if missing:
        status += f"Missing: {', '.join(missing)}\n"

    return status
