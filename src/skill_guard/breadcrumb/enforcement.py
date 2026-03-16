#!/usr/bin/env python3
"""
Breadcrumb Enforcement Level System

Defines three-tier enforcement levels for breadcrumb verification:
- MINIMAL: Basic tracking (duration > 10s + 2+ tools)
- STANDARD: Medium tracking (+ workflow ≥2 phases + verification)
- STRICT: Full tracking (all workflow_steps must complete)

Skills can override default level in SKILL.md frontmatter.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default enforcement level if not specified in SKILL.md
DEFAULT_ENFORCEMENT_LEVEL = "STANDARD"

# Environment variable to override enforcement level globally
ENFORCEMENT_LEVEL_ENV = "BREADCRUMB_ENFORCEMENT_LEVEL"


# =============================================================================
# ENUMERATION
# =============================================================================

class EnforcementLevel(Enum):
    """Breadcrumb enforcement levels.

    MINIMAL: Basic tracking - only checks duration and tool count
        - Duration > 10 seconds
        - At least 2 tools used
        - No workflow step verification

    STANDARD: Medium tracking - checks workflow phases
        - All MINIMAL checks
        - At least 2 workflow phases completed
        - Verification step completed

    STRICT: Full tracking - all steps must complete
        - All workflow steps must be completed
        - No exceptions
        - Blocks completion if any step missing
    """

    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    STRICT = "STRICT"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# LEVEL DETECTION
# =============================================================================

def get_enforcement_level(skill_name: str) -> EnforcementLevel:
    """Get enforcement level for a skill.

    Checks in order:
    1. Environment variable (global override)
    2. SKILL.md frontmatter (skill-specific)
    3. Default (STANDARD)

    Args:
        skill_name: Name of the skill (without slash)

    Returns:
        EnforcementLevel enum value
    """
    # 1. Check environment variable (global override)
    env_level = os.environ.get(ENFORCEMENT_LEVEL_ENV, "").upper()
    if env_level:
        try:
            return EnforcementLevel(env_level)
        except ValueError:
            pass  # Invalid value, fall through to next check

    # 2. Check SKILL.md frontmatter
    skill_dir = Path("P:/.claude/skills") / skill_name.lower()
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists():
        try:
            import yaml  # noqa: PLC0415
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            parts = content.split("---")
            if len(parts) >= 3:
                fm_data = yaml.safe_load(parts[1])
                if isinstance(fm_data, dict):
                    level_str = fm_data.get("enforcement_level", "")
                    if level_str:
                        level_str = str(level_str).upper()
                        try:
                            return EnforcementLevel(level_str)
                        except ValueError:
                            pass  # Invalid value, use default
        except Exception:
            pass  # Error reading frontmatter, use default

    # 3. Return default
    return EnforcementLevel(DEFAULT_ENFORCEMENT_LEVEL)


# =============================================================================
# TIERED VERIFICATION
# =============================================================================

def _normalize_workflow_step_ids(workflow_steps: list) -> list[str]:
    """Normalize workflow_steps to list of step IDs.

    Handles both string format and dict format with 'id' field.

    Args:
        workflow_steps: List of workflow steps (str or dict)

    Returns:
        List of step IDs as strings
    """
    return [
        step["id"] if isinstance(step, dict) else step
        for step in workflow_steps
    ]


def verify_with_enforcement(
    skill_name: str,
    trail: dict[str, Any] | None,
    duration_seconds: float = 0.0,
    tool_count: int = 0,
) -> tuple[bool, str]:
    """Verify breadcrumb trail with tiered enforcement.

    Args:
        skill_name: Name of the skill
        trail: Breadcrumb trail dict from get_breadcrumb_trail()
        duration_seconds: Session duration in seconds
        tool_count: Number of tools used in session

    Returns:
        (is_complete, message) tuple
    """
    # Get enforcement level for this skill
    level = get_enforcement_level(skill_name)

    # If no trail exists, no workflow steps declared
    if not trail:
        return True, f"No workflow steps declared (level: {level.value})"

    workflow_steps = trail.get("workflow_steps", [])
    completed_steps = trail.get("completed_steps", [])

    # No workflow steps declared
    if not workflow_steps:
        return True, f"No workflow steps declared (level: {level.value})"

    # Normalize workflow_steps to list of step IDs (handles both str and dict formats)
    workflow_step_ids = _normalize_workflow_step_ids(workflow_steps)

    # Apply tiered verification
    if level == EnforcementLevel.MINIMAL:
        return _verify_minimal(
            workflow_step_ids, completed_steps, duration_seconds, tool_count
        )
    elif level == EnforcementLevel.STANDARD:
        return _verify_standard(
            workflow_step_ids, completed_steps, duration_seconds, tool_count
        )
    else:  # STRICT
        return _verify_strict(
            workflow_step_ids, completed_steps, duration_seconds, tool_count
        )


def _verify_minimal(
    workflow_steps: list[str],
    completed_steps: list[str],
    duration_seconds: float,
    tool_count: int,
) -> tuple[bool, str]:
    """MINIMAL level: Check duration and tool count only."""
    # Duration check: > 10 seconds
    if duration_seconds <= 10.0:
        return False, (
            f"MINIMAL: Session too short ({duration_seconds:.1f}s ≤ 10s). "
            "Spend more time on the task or use STANDARD level."
        )

    # Tool count check: at least 2 tools
    if tool_count < 2:
        return False, (
            f"MINIMAL: Too few tools used ({tool_count} < 2). "
            "Use more tools or use STANDARD level."
        )

    # Workflow steps are not checked at MINIMAL level
    return True, f"MINIMAL: Duration {duration_seconds:.1f}s, {tool_count} tools (workflow steps not checked)"


def _verify_standard(
    workflow_steps: list[str],
    completed_steps: list[str],
    duration_seconds: float,
    tool_count: int,
) -> tuple[bool, str]:
    """STANDARD level: Check MINIMAL + workflow phases + verification."""
    # First apply MINIMAL checks
    minimal_complete, minimal_message = _verify_minimal(
        workflow_steps, completed_steps, duration_seconds, tool_count
    )
    if not minimal_complete:
        return False, minimal_message

    # Workflow phase check: at least 2 phases completed
    if len(completed_steps) < 2:
        return False, (
            f"STANDARD: Too few workflow steps completed ({len(completed_steps)} < 2). "
            f"Completed: {', '.join(completed_steps) or 'none'}"
        )

    # Verification step check: look for verification-related steps
    verification_keywords = ["verify", "check", "validate", "test", "review"]
    has_verification = any(
        any(kw in step.lower() for kw in verification_keywords)
        for step in completed_steps
    )

    if not has_verification:
        return False, (
            "STANDARD: No verification step completed. "
            "Complete verification, testing, or review step."
        )

    return True, f"STANDARD: {len(completed_steps)}/{len(workflow_steps)} steps complete (with verification)"


def _verify_strict(
    workflow_steps: list[str],
    completed_steps: list[str],
    duration_seconds: float,
    tool_count: int,
) -> tuple[bool, str]:
    """STRICT level: All workflow steps must complete."""
    # Check all workflow steps are completed
    missing_steps = [step for step in workflow_steps if step not in completed_steps]

    if missing_steps:
        return False, (
            f"STRICT: Missing workflow steps: {', '.join(missing_steps)}. "
            f"Completed: {len(completed_steps)}/{len(workflow_steps)}"
        )

    return True, f"STRICT: All {len(workflow_steps)} workflow steps completed"
