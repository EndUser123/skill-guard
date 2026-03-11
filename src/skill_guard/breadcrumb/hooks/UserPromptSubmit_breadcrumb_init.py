#!/usr/bin/env python3
"""
Breadcrumb Initialization Module for UserPromptSubmit Hook
=========================================================

Integrates breadcrumb trail initialization with skill invocation detection.

When a skill is invoked (detected via /skill-name pattern in user prompt),
this module initializes the breadcrumb trail for that skill.

Configuration:
- BREADCRUMB_INITIALIZATION_ENABLED (default: true) - Enable/disable auto-initialization

Author: Skill Enforcement v2.0
Date: 2026-03-10
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

# Add skill-guard to path
SKILL_GUARD = Path("P:/packages/skill-guard/src")
if SKILL_GUARD.exists():
    sys.path.insert(0, str(SKILL_GUARD))

# Configure logger (no stderr output - Claude Code treats stderr as hook error)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Configuration
BREADCRUMB_INITIALIZATION_ENABLED = os.environ.get("BREADCRUMB_INITIALIZATION_ENABLED", "true").lower() == "true"


# Pattern to detect skill invocations in user prompts
SKILL_INVOCATION_PATTERN = r"^/\s*([a-zA-Z][a-zA-Z0-9_-]*)"


def _extract_skill_name(prompt: str) -> str | None:
    """Extract skill name from user prompt.

    Args:
        prompt: User's input prompt

    Returns:
        Skill name (without slash) or None if no skill invocation detected
    """
    match = re.match(SKILL_INVOCATION_PATTERN, prompt.strip())

    if match:
        skill_name = match.group(1)
        return skill_name

    return None


def initialize_breadcrumb_for_skill(skill_name: str) -> bool:
    """Initialize breadcrumb trail for a skill.

    Args:
        skill_name: Name of the skill being invoked

    Returns:
        True if initialization succeeded, False otherwise
    """
    # Import breadcrumb components
    try:
        from skill_guard.breadcrumb.tracker import initialize_breadcrumb_trail
    except ImportError as e:
        logger.warning(f"Failed to import breadcrumb components: {e}")
        return False

    try:
        # Initialize breadcrumb trail
        initialize_breadcrumb_trail(skill_name)

        logger.info(f"Initialized breadcrumb trail for skill: {skill_name}")
        return True

    except Exception as e:
        logger.warning(f"Failed to initialize breadcrumb trail for {skill_name}: {e}")
        return False


def process_prompt_for_breadcrumbs(prompt: str, data: dict) -> str | None:
    """Process user prompt to initialize breadcrumbs for skill invocation.

    Args:
        prompt: User's input prompt
        data: UserPromptSubmit hook data

    Returns:
        Context injection string if breadcrumbs were initialized, None otherwise
    """
    # Check if breadcrumb initialization is enabled
    if not BREADCRUMB_INITIALIZATION_ENABLED:
        return None

    # Extract skill name from prompt
    skill_name = _extract_skill_name(prompt)

    if not skill_name:
        # No skill invocation detected
        return None

    # Initialize breadcrumb trail
    success = initialize_breadcrumb_for_skill(skill_name)

    if success:
        # Return user-facing skill invocation indicator
        indicator = (
            f"**🔧 Invoking Skill** /{skill_name}\n\n"
            f"Initializing breadcrumb trail for skill execution..."
        )
        return indicator

    return None


if __name__ == "__main__":
    # Test mode
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test with sample prompts
        test_prompts = [
            "/code implement feature",
            "/plan review architecture",
            "/ask question about code",
            "just write some code without skill",
        ]

        for prompt in test_prompts:
            skill_name = _extract_skill_name(prompt)
            result = process_prompt_for_breadcrumbs(prompt, {})
            print(f"Prompt: {prompt}")
            print(f"  Skill: {skill_name}")
            print(f"  Result: {result}")
            print()

        sys.exit(0)
