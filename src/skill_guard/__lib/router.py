#!/usr/bin/env python3
"""Skill-guard router - dispatches to the appropriate hook based on event type.

This router exists to work around GitHub issue #16288:
"Plugin hooks not loaded from external hooks.json file"

Since Claude Code doesn't load hooks.json from plugin directories, we register
a single hook in settings.json that dispatches to all skill-guard hooks.

Usage:
    python router.py <EventName>

Where EventName is PreToolUse, Stop, or UserPromptSubmit.
The router calls the same main functions the hook scripts would call.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure skill_guard package is importable
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

# Also ensure local hooks dir is importable (matches hook script behavior)
_MAIN_HOOKS_DIR = Path.home() / ".claude" / "hooks"
if _MAIN_HOOKS_DIR.exists():
    _s = str(_MAIN_HOOKS_DIR)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from skill_guard.execution_hooks import pre_tool_use_main, stop_main
from skill_guard.user_prompt_submit_hook import user_prompt_submit_main

_DISPATCH = {
    "PreToolUse": pre_tool_use_main,
    "Stop": stop_main,
    "UserPromptSubmit": user_prompt_submit_main,
}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    event_type = sys.argv[1]
    handler = _DISPATCH.get(event_type)
    if handler is None:
        sys.exit(0)

    handler()


if __name__ == "__main__":
    main()
