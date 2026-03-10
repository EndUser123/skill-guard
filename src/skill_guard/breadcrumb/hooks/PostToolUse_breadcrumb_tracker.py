#!/usr/bin/env python3
"""
PostToolUse - Automatic Breadcrumb Tracking Hook
==================================================

Automatically tracks workflow steps by inferring them from tool usage.

Uses the tool pattern inference system to map Claude Code tools to workflow steps:
- WebSearch → research
- Read → requirements
- Edit/Write → tdd
- Bash → verification
- etc.

This enables automatic breadcrumb tracking without manual set_breadcrumb() calls.

Configuration:
- BREADCRUMB_AUTO_TRACKING_ENABLED (default: true) - Enable/disable auto-tracking
- BREADCRUMB_AUTO_TRACKING_MODE (default: advisory) - warn or block modes

Author: Skill Enforcement v2.0
Date: 2026-03-10
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add skill-guard to path
SKILL_GUARD = Path("P:/packages/skill-guard/src")
if SKILL_GUARD.exists():
    sys.path.insert(0, str(SKILL_GUARD))

# Configure logger (no stderr output - Claude Code treats stderr as hook error)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Configuration from environment
BREADCRUMB_AUTO_TRACKING_ENABLED = os.environ.get("BREADCRUMB_AUTO_TRACKING_ENABLED", "true").lower() == "true"
BREADCRUMB_AUTO_TRACKING_MODE = os.environ.get("BREADCRUMB_AUTO_TRACKING_MODE", "advisory")


def _get_current_skill(data: dict) -> str | None:
    """Extract current skill name from tool usage context.

    Args:
        data: PostToolUse hook input data

    Returns:
        Skill name (without slash) or None if not in a skill context
    """
    # Check if tool_name indicates skill invocation
    tool_name = data.get("tool_name", "")

    # Skill tool invocations have this pattern
    if tool_name == "Skill":
        tool_input = data.get("tool_input", {})
        skill_with_args = tool_input.get("skill", "")

        # Extract skill name (remove leading slash)
        if skill_with_args.startswith("/"):
            skill_name = skill_with_args[1:].split()[0]  # Remove / and split on args
            return skill_name
        elif skill_with_args:
            # No leading slash but still a skill invocation
            skill_name = skill_with_args.split()[0]
            return skill_name

    return None


def run(data: dict) -> dict | None:
    """PostToolUse hook entry point for automatic breadcrumb tracking.

    Args:
        data: PostToolUse hook input with keys:
            - tool_name: Name of the tool that was used
            - tool_input: Input parameters passed to the tool
            - tool_response: Response from the tool execution

    Returns:
        Warning dict if tracking succeeded, None otherwise
        {
            "warning": "Auto-tracked step: tdd (from Edit tool)"
        }
    """
    # Check if auto-tracking is enabled
    if not BREADCRUMB_AUTO_TRACKING_ENABLED:
        return None

    # Import breadcrumb components
    try:
        from skill_guard.breadcrumb.inference import infer_step_from_tool_use
        from skill_guard.breadcrumb.tracker import set_breadcrumb
    except ImportError as e:
        logger.warning(f"Failed to import breadcrumb components: {e}")
        return None

    # Get current skill context
    skill_name = _get_current_skill(data)

    if not skill_name:
        # Not in a skill context, skip tracking
        return None

    # Infer workflow step from tool usage
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    inferred_step = infer_step_from_tool_use(tool_name, tool_input)

    if not inferred_step:
        # No inference possible for this tool
        return None

    # Set breadcrumb automatically
    try:
        set_breadcrumb(skill_name, inferred_step)

        # Log successful tracking
        logger.info(f"Auto-tracked step: {inferred_step} (from {tool_name} tool in {skill_name} skill)")

        # Return warning for visibility (advisory mode)
        if BREADCRUMB_AUTO_TRACKING_MODE == "advisory":
            return {
                "warning": f"Auto-tracked step: {inferred_step} (from {tool_name} tool)"
            }

        return None

    except Exception as e:
        logger.warning(f"Failed to set breadcrumb: {e}")
        return None


if __name__ == "__main__":
    # Test mode
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test with sample data
        test_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "test.py"},
            "tool_response": ""
        }

        result = run(test_data)
        print(f"Result: {result}")
        sys.exit(0)
