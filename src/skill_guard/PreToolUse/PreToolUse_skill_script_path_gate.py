#!/usr/bin/env python3
r"""
Skill Script Path Gate v1.0
============================

Blocks Bash commands that invoke a Python script at a P:\\\\\ path that does not
exist on disk.  Catches stale absolute paths hardcoded in SKILL.md files before
the LLM silently runs against a missing file.

Root causes addressed:
  RC2 - Skill authoring has no validation loop (runtime safety net)
  RC3 - Hooks cover tool events, not reasoning steps (blocks at execution)

Pattern detected:
  python r"P:\\\\\.claude\\skills\\<name>\\<script>.py" ...
  python r'P:\\\\.claude/skills/<name>/<script>.py' ...
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Matches: python r"P:\\\\..." or python r'P:\\\\...' or python P:\\\\... (unquoted)
# Handles both backslash and forward-slash Windows paths.
_PATTERN = re.compile(
    r"""python(?:3)?\s+[r"']?(P:[/\\][^"r'\s]+\.py)["']?""",
    re.IGNORECASE,
)

HOOK_NAME = "PreToolUse_skill_script_path_gate.py"


def _extract_script_path(command: str) -> str | None:
    """Return the first P:-rooted .py path found in command, or None."""
    m = _PATTERN.search(command)
    if not m:
        return None
    raw = m.group(1)
    # Normalise separators for Path resolution on Windows
    return raw.replace("/", "\\")


def run(data: dict) -> dict | None:
    """In-process entry point. Returns block dict or None to allow."""
    if data.get("tool_name") != "Bash":
        return None

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        return None

    script_path = _extract_script_path(command)
    if not script_path:
        return None

    if Path(script_path).exists():
        return None

    return {
        "decision": "block",
        "reason": (
            f"⛔ SKILL SCRIPT NOT FOUND: {script_path}\n\n"
            "The SKILL.md hardcodes a path that does not exist on disk.\n"
            "This is a stale path — the skill was likely renamed or moved.\n\n"
            "Fix options:\n"
            f"  1. Check the correct path:  dir \"{Path(script_path).parent}\"\n"
            f"  2. Update SKILL.md Step 1 to point at the correct script\n"
            f"  3. Verify skill name matches directory: "
            f"dir \"P:\\\\\.claude\\skills\\\"\n\n"
            "Do NOT fabricate results or provide your own analysis as a substitute."
        ),
        "blocking_hook": HOOK_NAME,
    }


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    result = run(data)
    if result:
        print(json.dumps(result))
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
