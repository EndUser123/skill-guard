#!/usr/bin/env python3
"""
Skill Execution State Management
=================================

Shared state management for skill execution tracking.
Used by both PreToolUse_skill_pattern_gate and skill_execution_tracker.

Provides terminal-isolated state storage for skill execution validation.

v3.5 CHANGES:
- Added first_tool_coherence tracking for intent-tool validation
- Skills declaring allowed_first_tools in frontmatter get first-tool gating
- Knowledge/consultation skills (ask, discover, etc.) now participate in
  coherence checking when they declare allowed_first_tools metadata
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # pyyaml declared as optional dependency

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")
HOOKS_LIB_DIR = Path("P:/.claude/hooks/__lib")

# =============================================================================
# SKILL EXECUTION REGISTRY (Reference for validation)
# =============================================================================
# Import registry for validation - loaded lazily to avoid circular imports
_SKILL_EXECUTION_REGISTRY = None


def _get_skill_execution_registry():
    """Load SKILL_EXECUTION_REGISTRY from PreToolUse hook if available.

    Returns empty dict if PreToolUse_skill_pattern_gate is not found.
    This allows the library to work without hook dependencies.
    """
    global _SKILL_EXECUTION_REGISTRY
    if _SKILL_EXECUTION_REGISTRY is None:
        _SKILL_EXECUTION_REGISTRY = {}
    return _SKILL_EXECUTION_REGISTRY


# =============================================================================
# TERMINAL DETECTION
# =============================================================================


def detect_terminal_id() -> str:
    """Detect terminal ID for state isolation.

    Uses terminal_detection.py from utils for consistent ID detection.
    """
    try:
        # Import shared terminal detection from utils
        from skill_guard.utils.terminal_detection import detect_terminal_id as shared_detect

        return shared_detect()
    except ImportError:
        # Fallback if terminal_detection not available. Do not synthesize
        # PID-based IDs because they break cross-hook state sharing.
        terminal_id = os.environ.get("CLAUDE_TERMINAL_ID")
        if terminal_id:
            return terminal_id
        return ""


# =============================================================================
# STATE MANAGEMENT
# =============================================================================


def _get_state_file() -> Path:
    """Legacy path retained for compatibility only."""
    terminal_id = detect_terminal_id()
    state_subdir = STATE_DIR / f"skill_execution_{terminal_id}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    return state_subdir / "skill_execution_pending.json"


def _get_state_dir() -> Path:
    """Get the state directory for this terminal."""
    terminal_id = detect_terminal_id()
    state_subdir = STATE_DIR / f"skill_execution_{terminal_id}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    return state_subdir


def _load_skill_frontmatter(skill_name: str) -> dict[str, Any]:
    """Load allowed_first_tools from a skill's SKILL.md frontmatter.

    Reads the skill's YAML frontmatter and extracts the allowed_first_tools
    field if present. This metadata is captured by the skill_registry's
    catch-all metadata dict.

    Args:
        skill_name: Skill name (without slash)

    Returns:
        Dict with frontmatter fields used by execution/governance tracking.
    """
    result: dict[str, Any] = {
        "allowed_first_tools": [],
        "layer1_enforcement": False,
        "usage_markers": [],
    }
    skill_dir = Path("P:/.claude/skills") / skill_name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return result

    if yaml is None:
        return result

    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return result
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return result
        aft = fm_data.get("allowed_first_tools", [])
        if isinstance(aft, list):
            result["allowed_first_tools"] = [str(t) for t in aft]
        usage_markers = fm_data.get("usage_markers", [])
        if isinstance(usage_markers, list):
            result["usage_markers"] = [
                str(marker) for marker in usage_markers if str(marker).strip()
            ]
        result["layer1_enforcement"] = bool(fm_data.get("layer1_enforcement"))
    except Exception:
        pass
    return result


def _get_ledger_module():
    """Import hook_ledger from the hooks library."""
    if HOOKS_LIB_DIR.exists() and str(HOOKS_LIB_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_LIB_DIR))
    import hook_ledger  # type: ignore

    return hook_ledger


def _get_active_turn_scope() -> tuple[str, str]:
    """Return (terminal_id, turn_id) for the current terminal."""
    terminal_id = detect_terminal_id()
    if not terminal_id:
        return "", ""
    try:
        ledger = _get_ledger_module()
        turn_id = ledger.get_active_turn(terminal_id) or ""
        return terminal_id, str(turn_id)
    except Exception:
        return terminal_id, ""


def set_skill_loaded(
    skill_name: str,
    required_tools: list[str] | None = None,
    pattern: str | None = None,
    hint: str = "",
    intent_enabled: bool = False,
    prompt_fingerprint: str = "",
    task_id: str = "",
) -> None:
    """Called when Skill tool is used.

    Args:
        skill_name: Name of the skill being loaded
        required_tools: List of tools that count as execution
        pattern: Regex pattern that must match in commands
        hint: User-facing hint message when blocked
        intent_enabled: Whether daemon semantic validation is enabled
    """
    skill_lower = skill_name.lower()

    # Load frontmatter metadata (allowed_first_tools) for ALL skills,
    # including knowledge skills — this enables first-tool coherence
    # checking even for consultation/discovery skills like /ask.
    frontmatter = _load_skill_frontmatter(skill_lower)
    allowed_first_tools = frontmatter.get("allowed_first_tools", [])

    # Load registry if config not provided
    if required_tools is None or pattern is None:
        # Try to load from PreToolUse_skill_pattern_gate if available
        # Use _get_skill_execution_registry() which handles import failures gracefully
        registry = _get_skill_execution_registry()
        skill_config = registry.get(skill_lower, {})
        required_tools = skill_config.get("tools", [])
        pattern = skill_config.get("pattern", "")
        hint = skill_config.get("hint", "")
        intent_enabled = skill_config.get("intent_enabled", False)

        # VALIDATION: Detect skills in registry with empty required_tools
        # This is RISK:9 mitigation - prevent security gaps from misconfigured skills
        if skill_lower in registry and not required_tools:
            warning_msg = (
                f"[skill_execution_state] WARNING: Skill '{skill_lower}' is in "
                f"SKILL_EXECUTION_REGISTRY but has empty required_tools. This will be treated "
                f"as a knowledge skill (no execution validation). Fix: Add 'tools' field to "
                f"registry entry or remove from registry if this is a knowledge skill."
            )
            sys.stderr.write(warning_msg + "\n")

    # Only write state if skill has execution requirements or first-tool coherence
    # Knowledge skills (required_tools=[] and no allowed_first_tools) don't need state tracking
    # This makes the system multi-terminal safe and immune to stale data
    if not required_tools and not allowed_first_tools:
        return  # Pure knowledge skill - no state needed

    # Create state payload
    state = {
        "skill": skill_lower,
        "loaded_at": time.time(),
        "required_tools": required_tools,
        "pattern": pattern,
        "output_markers": [],
        # v3.2 extended schema
        "required_pattern": pattern,  # Same as pattern
        "hint": hint,
        "intent_enabled": intent_enabled,
        "prompt_fingerprint": str(prompt_fingerprint or ""),
        "task_id": str(task_id or ""),
        "tools_used": [],
        "commands_run": [],
        "execution_satisfied": False,
        # v3.5: first-tool coherence tracking
        "allowed_first_tools": allowed_first_tools,
        "first_tool_validated": False,
    }

    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        return

    try:
        ledger = _get_ledger_module()
        ledger.append_event(
            terminal_id,
            turn_id,
            "PostToolUse",
            "skill_loaded",
            state,
        )
        if frontmatter.get("layer1_enforcement") and frontmatter.get("usage_markers"):
            ledger.append_event(
                terminal_id,
                turn_id,
                "PostToolUse",
                "governance_expected",
                {
                    "skill": skill_lower,
                    "markers": frontmatter.get("usage_markers", []),
                },
            )
    except Exception:
        pass


def record_tool_use(tool_name: str, tool_input: dict[str, Any]) -> None:
    """Record tool usage for execution validation.

    Args:
        tool_name: Name of the tool being used
        tool_input: Input parameters passed to the tool
    """
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        return

    try:
        command = ""
        if tool_name == "Bash":
            command = tool_input.get("command", "")
        elif tool_name == "Task":
            command = tool_input.get("prompt", "")
        ledger = _get_ledger_module()
        ledger.append_event(
            terminal_id,
            turn_id,
            "PostToolUse",
            "skill_tool_used",
            {
                "tool_name": tool_name,
                "command": str(command or ""),
                "tool_input": tool_input if isinstance(tool_input, dict) else {},
            },
        )
    except Exception:
        pass


def read_pending_state() -> dict | None:
    """Read current skill execution state from state file.

    Returns:
        State dict or None if no skill loaded
    """
    try:
        terminal_id, turn_id = _get_active_turn_scope()
        if not terminal_id or not turn_id:
            return None
        ledger = _get_ledger_module()
        snapshot = ledger.materialize_turn(terminal_id, turn_id)
        state = snapshot.get("skill_state")
        if isinstance(state, dict):
            return state
    except Exception:
        return None
    return None


def mark_first_tool_validated() -> None:
    """Mark that the first tool call passed coherence check.

    Called by PreToolUse_skill_pattern_gate after validating the first
    non-investigation tool matches the skill's allowed_first_tools.
    Subsequent tool calls skip the coherence check.
    """
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        return

    try:
        ledger = _get_ledger_module()
        ledger.append_event(
            terminal_id,
            turn_id,
            "PreToolUse",
            "skill_first_tool_validated",
            {"validated": True},
        )
    except Exception:
        pass


def clear_state() -> None:
    """Clear current skill execution state for the active turn."""
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        return
    try:
        ledger = _get_ledger_module()
        ledger.append_event(
            terminal_id,
            turn_id,
            "Stop",
            "skill_state_cleared",
            {"cleared_at": time.time()},
        )
    except Exception:
        pass


# =============================================================================
# MIGRATION HELPERS
# =============================================================================


def migrate_legacy_state() -> None:
    """Migrate state from old location to new terminal-isolated location.

    This handles backward compatibility with state files created
    before v3.2 terminal isolation.

    Call this function explicitly from hooks or scripts when needed.
    Migration is no longer automatic on import to avoid side effects.
    """
    # Check for legacy state file
    legacy_state = STATE_DIR / "skill_execution_pending.json"
    if not legacy_state.exists():
        return

    try:
        # Read legacy state
        legacy_data = json.loads(legacy_state.read_text())

        # Extend schema if missing fields (v3.2 backward compatibility)
        if "required_pattern" not in legacy_data:
            legacy_data["required_pattern"] = legacy_data.get("pattern", "")
        if "hint" not in legacy_data:
            legacy_data["hint"] = ""
        if "intent_enabled" not in legacy_data:
            legacy_data["intent_enabled"] = False

        # Write to new location
        new_state_file = _get_state_file()
        new_state_file.parent.mkdir(parents=True, exist_ok=True)
        new_state_file.write_text(json.dumps(legacy_data, indent=2))

        # Remove legacy file
        legacy_state.unlink()

    except (json.JSONDecodeError, OSError):
        pass
