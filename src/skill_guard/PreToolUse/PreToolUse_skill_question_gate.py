"""PreToolUse hook for one-question-max enforcement.

Tracks question-marking turns between skill invocation and execution.
Blocks if more than one question is emitted before the skill executes.

The actual question detection is done by Stop_skill_question_marker.py (Stop hook).
This PreToolUse hook checks the question count and resets on Skill/tool execution.

From ADR-20260329-llm-consultation-pattern-fix.md — CHANGE-003
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add hooks dir to path for __lib imports (hardcoded — __file__ resolves to plugin dir)
_HOOKS_DIR = r"P:/.claude/hooks"
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from __lib.file_lock import FileLock

# State directory
_STATE_DIR = Path.home() / ".claude" / "hooks" / "state"

# Marker file set by Stop hook when a question is seen
_QUESTION_MARKER = "question_asked_{session_id}.json"

# Skill invocation marker
_SKILL_MARKER = "skill_invoked_{session_id}.json"


def _get_marker_path(session_id: str, prefix: str) -> Path:
    if not session_id:
        return Path("/dev/null")
    return _STATE_DIR / prefix.format(session_id=session_id)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    lock = FileLock(lock_path, timeout=5.0)
    with lock:
        path.write_text(json.dumps(data), encoding="utf-8")


def run(data: dict[str, Any]) -> dict[str, Any]:
    """Enforce one-question-max for skill invocations.

    Design:
    - Stop_skill_question_marker.py sets a marker when the LLM asks a question
    - This hook checks the marker on every tool call
    - Skill tool invocation: reset everything
    - Non-Skill tool: consume marker if present, reset on any tool execution

    Args:
        data: Hook data containing tool_name, tool_input, etc.

    Returns:
        Dictionary with 'continue' (bool) and optional 'reason' (str)
    """
    if os.environ.get("SKILL_QUESTION_GATE_ENABLED", "true").lower() != "true":
        return {"continue": True}

    tool_name = data.get("tool_name", "")
    session_id = str(data.get("session_id", ""))

    if not session_id:
        return {"continue": True}

    skill_marker = _get_marker_path(session_id, _SKILL_MARKER)
    question_marker = _get_marker_path(session_id, _QUESTION_MARKER)

    if tool_name == "Skill":
        # Skill invoked: mark it, reset question count
        _save_json(skill_marker, {"invoked": True})
        # Clear any existing question marker
        if question_marker.exists():
            question_marker.unlink(missing_ok=True)
        return {"continue": True}

    # Non-Skill tool: any tool execution resets the question counter
    # (user is engaging, not just asking questions)
    if skill_marker.exists():
        # Skill was invoked — consume the question marker
        q_state = _load_json(question_marker)
        if q_state.get("count", 0) > 1:
            # More than one question asked before execution — block
            return {
                "continue": False,
                "reason": (
                    "ONE-QUESTION-MAX EXCEEDED\n\n"
                    "You asked more than one question before executing the skill.\n"
                    "Execute the skill directly instead of asking additional questions.\n\n"
                    "Rule: When a skill is invoked, execute immediately if context is sufficient.\n"
                    "If context is ambiguous, ask exactly ONE question, then execute.\n\n"
                    "To disable: export SKILL_QUESTION_GATE_ENABLED=false"
                ),
            }
        # Allow — but reset markers (execution has started)
        if skill_marker.exists():
            skill_marker.unlink(missing_ok=True)
        if question_marker.exists():
            question_marker.unlink(missing_ok=True)

    return {"continue": True}


if __name__ == "__main__":
    try:
        raw = sys.stdin.read().strip()
        input_data = json.loads(raw) if raw else {}
    except Exception:
        input_data = {}

    result = run(input_data)
    print(json.dumps(result))

