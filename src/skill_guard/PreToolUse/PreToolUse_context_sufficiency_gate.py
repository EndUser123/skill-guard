"""PreToolUse hook for skill context-sufficiency classification.

Checks if a skill invocation has sufficient deterministic context to execute immediately
(PRE_AUTHORIZED tier) or needs one question (AMBIGUOUS tier).

From ADR-20260329-llm-consultation-pattern-fix.md — CHANGE-002
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Add skills __lib to path for registry import (hardcoded — __file__ resolves to plugin dir)
_SKILLS_LIB = r"P:/.claude/hooks/skills/__lib"
if _SKILLS_LIB not in sys.path:
    sys.path.insert(0, _SKILLS_LIB)


def _load_skill_autonomy_registry():
    """Lazy-load the registry to avoid import errors if not present."""
    try:
        from skill_autonomy_registry import classify_skill_invocation, Tier
        return classify_skill_invocation, Tier
    except ImportError:
        return None, None


def run(data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate if a Skill tool invocation has sufficient context.

    Args:
        data: Hook data containing tool_name, tool_input, etc.

    Returns:
        Dictionary with 'continue' (bool) and optional 'reason' (str)
    """
    tool_name = data.get("tool_name", "")

    # Only act on Skill tool invocations
    if tool_name != "Skill":
        return {"continue": True}

    # Check if gate is enabled
    if os.environ.get("CONTEXT_SUFFICIENCY_GATE_ENABLED", "true").lower() != "true":
        return {"continue": True}

    tool_input = data.get("tool_input", {})
    skill_name = tool_input.get("skill", "") or ""
    skill_args = tool_input.get("args", "") or ""

    # Build args dict for registry
    args: dict = {}
    if isinstance(skill_args, dict):
        args = skill_args
    elif isinstance(skill_args, str) and skill_args.strip():
        # Try JSON first
        try:
            parsed = json.loads(skill_args)
            if isinstance(parsed, dict):
                args = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    classify_fn, tier_enum = _load_skill_autonomy_registry()
    if classify_fn is None or tier_enum is None:
        # Registry not available — allow (fail open)
        return {"continue": True}

    classification = classify_fn(skill_name, args)

    if classification.tier == tier_enum.PRE_AUTHORIZED:
        return {
            "continue": True,
            "reason": f"Context-sufficient: {skill_name} with deterministic input — execute immediately",
        }
    elif classification.tier == tier_enum.AMBIGUOUS:
        return {
            "continue": True,
            "reason": f"Ambiguous: {skill_name} — one question permitted before execution",
        }
    elif classification.tier == tier_enum.BLOCKING:
        return {
            "continue": False,
            "reason": (
                f"Blocking: {skill_name} is a high-risk operation.\n"
                "Skill invocation requires explicit approval.\n"
                "To disable: export CONTEXT_SUFFICIENCY_GATE_ENABLED=false"
            ),
        }

    return {"continue": True}


if __name__ == "__main__":
    try:
        raw = sys.stdin.read().strip()
        input_data = json.loads(raw) if raw else {}
    except Exception:
        input_data = {}

    result = run(input_data)
    print(json.dumps(result))
