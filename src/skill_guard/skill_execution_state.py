#!/usr/bin/env python3
r"""
Skill Execution State Management
=================================

Shared state management for skill execution tracking.
Used by both PreToolUse_skill_pattern_gate and skill_execution_tracker.

Provides terminal-isolated state storage for skill execution validation.

v3.5 CHANGES:
- Added first_tool_coherence tracking for intent-tool validation
- Skills declaring allowed_first_tools in frontmatter get first-tool gating
- Skills can also declare required_first_command_patterns to enforce the
  first backend command after Skill()
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

# Import pure frontmatter parsing from dedicated module
from skill_guard._skill_frontmatter_loader import (
    _normalize_string_list as _shared_normalize,
    _infer_contract_type,
    _load_skill_frontmatter as _shared_load,
    _validate_skill_frontmatter as _shared_validate,
)

# Re-export so existing callers continue to work
_normalize_string_list = _shared_normalize

# Import phase constants from dedicated module
from skill_guard.phases import (
    _PHASE_PENDING,
    _PHASE_LOADED,
    _PHASE_EXECUTING,
    _PHASE_COMPLETE,
    _PHASE_STALE,
    VALID_TRANSITIONS,
    DEFAULT_STALE_TIMEOUT,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path(r"P:\\\\.claude/.state")
HOOKS_LIB_DIR = Path(r"P:\\\\.claude/hooks/__lib")

# _normalize_string_list, _infer_contract_type now delegated to _skill_frontmatter_loader
_VALID_CONTRACT_TYPES = {"workflow", "output", "hybrid", "analysis"}

# _get_legacy_skill_metadata_cache is used by tests - keep as compatibility shim
_LEGACY_SKILL_METADATA_CACHE = None


def _get_legacy_skill_metadata_cache():
    global _LEGACY_SKILL_METADATA_CACHE
    if _LEGACY_SKILL_METADATA_CACHE is None:
        _LEGACY_SKILL_METADATA_CACHE = {}
    return _LEGACY_SKILL_METADATA_CACHE


# =============================================================================
# TERMINAL DETECTION
# =============================================================================


def detect_terminal_id() -> str:
    """Detect terminal ID for state isolation.

    Uses terminal_detection.py from utils for consistent ID detection.
    r"""
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


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON data atomically using write-to-temp-then-rename pattern.

    Uses gc.collect() + retry for Windows handle release, then rename.
    Falls back to direct write on repeated failure to avoid blocking.
    """
    import gc

    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(json.dumps(data, indent=2))
        os.replace(str(temp), str(path))
    except OSError:
        # Windows: file handle still held. Retry after gc to release handles.
        gc.collect()
        try:
            temp.write_text(json.dumps(data, indent=2))
            os.replace(str(temp), str(path))
        except OSError:
            # Final fallback: direct write (not atomic, but wonr't orphan temp)
            path.write_text(json.dumps(data, indent=2))


def sanitize_terminal_id(terminal_id: str) -> str:
    """Sanitize terminal ID for use in file paths.

    Removes characters that are unsafe for filesystem paths.
    Only allows alphanumeric, underscore, and hyphen. Colon is excluded
    because it causes issues on Windows (drive letter separator).
    """
    import re

    return re.sub(r"[^a-zA-Z0-9_\-]", "_", terminal_id)


def _get_state_file() -> Path:
    """Legacy path retained for compatibility only."""
    terminal_id = detect_terminal_id()
    state_subdir = STATE_DIR / f"skill_execution_{sanitize_terminal_id(terminal_id or 'unknown')}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    return state_subdir / "skill_execution_pending.json"


# Cached state directory per terminal_id (avoids repeated mkdir on every call)
_state_dir_cache: dict[str, Path] = {}


def _get_state_dir() -> Path:
    """Get the state directory for this terminal.

    Caches the result per terminal_id to avoid repeated directory
    creation syscalls on every invocation.
    """
    terminal_id = detect_terminal_id()
    cache_key = sanitize_terminal_id(terminal_id or "unknown")
    if cache_key in _state_dir_cache:
        return _state_dir_cache[cache_key]
    state_subdir = STATE_DIR / f"skill_execution_{cache_key}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    _state_dir_cache[cache_key] = state_subdir
    return state_subdir


def _get_state_file_for_terminal(terminal_id: str) -> Path:
    """Return the compatibility state file for a specific terminal."""
    state_subdir = STATE_DIR / f"skill_execution_{sanitize_terminal_id(terminal_id or 'unknown')}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    return state_subdir / "skill_execution_pending.json"


def _read_pending_state_file(terminal_id: str) -> dict[str, Any] | None:
    state_file = _get_state_file_for_terminal(terminal_id)
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write_pending_state_file(terminal_id: str, state: dict[str, Any]) -> bool:
    try:
        _atomic_write_json(_get_state_file_for_terminal(terminal_id), state)
        return True
    except OSError:
        return False


def _clear_pending_state_file(terminal_id: str) -> None:
    try:
        _get_state_file_for_terminal(terminal_id).unlink(missing_ok=True)
    except OSError:
        pass


# _load_skill_frontmatter now delegated to _skill_frontmatter_loader
def _load_skill_frontmatter(skill_name: str) -> dict[str, Any] | None:
    """Wrapper that delegates to _skill_frontmatter_loader.

    Returns None when skill file doesn't exist or canr't be parsed.
    """
    return _shared_load(skill_name)


# _validate_skill_frontmatter now delegated to _skill_frontmatter_loader
_validate_skill_frontmatter = _shared_validate


def _get_active_turn_scope() -> tuple[str, str]:
    """Return (terminal_id, turn_id) for the current terminal."""
    terminal_id = detect_terminal_id()
    if not terminal_id:
        return "", ""
    try:
        # Add hooks directory to path for evidence_store import
        hooks_dir = Path(r"P:\\\\.claude/hooks")
        if hooks_dir.exists() and str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from evidence_store import get_active_turn

        session_id = str(os.environ.get("CLAUDE_SESSION_ID", "")).strip()
        turn_id = get_active_turn(session_id, terminal_id) or ""
        return terminal_id, str(turn_id)
    except Exception:
        return terminal_id, ""


# =============================================================================
# LEDGER MODULE INTEGRATION
# =============================================================================

# Module-level cache for hook_ledger (pattern from the legacy metadata cache)
_HOOKS_LEDGER_MODULE = None


def _get_ledger_module():
    """Import and return hook_ledger module from Claude Code hooks.

    Returns:
        hook_ledger module if available, None otherwise.

    Note:
    Follows the same lazy-import pattern as the legacy metadata cache.
        Uses the same path manipulation as breadcrumb/tracker.py.
    r"""
    global _HOOKS_LEDGER_MODULE
    if _HOOKS_LEDGER_MODULE is not None:
        return _HOOKS_LEDGER_MODULE

    try:
        if HOOKS_LIB_DIR.exists() and str(HOOKS_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_LIB_DIR))
        import hook_ledger  # type: ignore

        _HOOKS_LEDGER_MODULE = hook_ledger
        return hook_ledger
    except Exception:
        return None


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

    # Load frontmatter metadata for ALL skills, including knowledge skills.
    # This enables first-tool coherence and first-command enforcement.
    frontmatter = _load_skill_frontmatter(skill_lower) or {}
    allowed_first_tools = frontmatter.get("allowed_first_tools", [])
    required_first_command_patterns = frontmatter.get("required_first_command_patterns", [])
    required_first_command_hint = frontmatter.get("required_first_command_hint", "")

    # Validate frontmatter for required fields and enforcement tier
    frontmatter_warnings = _validate_skill_frontmatter(skill_lower)

    # Load discovered skill config if config not provided
    if required_tools is None or pattern is None:
        # Use auto-discovery from the skill files as the source of truth.
        # This avoids relying on hardcoded per-skill tables.
        try:
            from skill_guard.skill_auto_discovery import get_skill_config

            skill_config = get_skill_config(skill_lower, None)
        except Exception:
            skill_config = {}
        required_tools = skill_config.get("tools", [])
        pattern = skill_config.get("pattern", "")
        hint = skill_config.get("hint", "")
        intent_enabled = skill_config.get("intent_enabled", False)

    # Only write state if skill has execution requirements, first-tool coherence,
    # or meaningful frontmatter (which distinguishes from accidental knowledge skills).
    # This makes the system multi-terminal safe and immune to stale data.
    # Knowledge skills with missing frontmatter: no tracking needed.
    # Knowledge skills with complete frontmatter: track anyway (complete metadata).
    # R3 FIX: When frontmatter_warnings is non-empty, always write state so the
    # consumer can display the warnings — even for pure knowledge skills.
    enforcement_tier = str(frontmatter.get("enforcement_tier", "") or "").strip().lower()
    if (
        enforcement_tier == "none"
        and not required_tools
        and not allowed_first_tools
        and not required_first_command_patterns
        and not frontmatter_warnings
    ):
        return
    if not required_tools and not allowed_first_tools and not required_first_command_patterns:
        # No execution requirements and no first-tool coherence.
        # Skip tracking for pure knowledge skills (no metadata at all).
        # We use frontmatter as the signal: if _load_skill_frontmatter returned
        # an empty dict (no file exists at P:\\\\.claude/skills/), skip state.
        # This avoids redundant file I/O — we already loaded frontmatter above.
        # R3: frontmatter_warnings non-empty always wins — warnings must be recorded.
        if not frontmatter_warnings and not frontmatter:
            return  # Truly a knowledge skill with no metadata - no state needed

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
        "terminal_id": "",
        "turn_id": "",
        "phase": _PHASE_PENDING,
        "updated_at": time.time(),
        "tools_used": [],
        "commands_run": [],
        "execution_satisfied": False,
        # v3.5: first-tool coherence tracking
        "allowed_first_tools": allowed_first_tools,
        "first_tool_validated": False,
        "required_first_command_patterns": required_first_command_patterns,
        "required_first_command_hint": required_first_command_hint,
        "contract_type": frontmatter.get("contract_type", ""),
        "required_phase_artifacts": frontmatter.get("required_phase_artifacts", []),
        "workflow_binding": frontmatter.get("workflow_binding", ""),
        "workflow_enforcement": frontmatter.get("workflow_enforcement", ""),
        "phase_recovery_mode": frontmatter.get("phase_recovery_mode", ""),
        "user_override": frontmatter.get("user_override", ""),
        "output_enforcement": frontmatter.get("output_enforcement", ""),
        "final_output_schema": frontmatter.get("final_output_schema", ""),
        "required_markers": frontmatter.get("required_markers", []),
        "required_sections": frontmatter.get("required_sections", []),
        "layer1_enforcement": bool(frontmatter.get("layer1_enforcement")),
        "usage_markers": frontmatter.get("usage_markers", []),
        "first_command_validated": False,
        # v4.0: workflow stage for topic drift prevention
        "workflow_stage": {
            "active_step": "",
            "step_definition": "",
            "done_criteria": [],
            "do_not_distract": [],
            "step_index": 0,
            "total_steps": 0,
        },
        # Frontmatter validation warnings
        "frontmatter_warnings": frontmatter_warnings,
        "completion_criteria": frontmatter.get("completion_criteria", []),
        "enforcement_tier": str(frontmatter.get("enforcement_tier", "") or "").strip(),
    }

    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        if not terminal_id:
            return
        _write_pending_state_file(terminal_id, state)
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
        _write_pending_state_file(terminal_id, state)
    except Exception:
        _write_pending_state_file(terminal_id, state)


def record_tool_use(tool_name: str, tool_input: dict[str, Any]) -> None:
    """Record tool usage for execution validation.

    Args:
        tool_name: Name of the tool being used
        tool_input: Input parameters passed to the tool
    r"""
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


def transition_phase(to_state: str) -> bool:
    """Transition the current skill state to a new phase.

    Args:
        to_state: The target phase (pending -> loaded -> executing -> complete/stale)

    Returns:
        True if transition succeeded, False if invalid transition or no state file
    """
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id:
        return False

    if turn_id:
        try:
            ledger = _get_ledger_module()
            snapshot = ledger.materialize_turn(terminal_id, turn_id)
            state = snapshot.get("skill_state", {})
            if not isinstance(state, dict):
                state = {}
            from_phase = state.get("phase", _PHASE_PENDING)

            allowed = VALID_TRANSITIONS.get(from_phase, [])
            if to_state not in allowed:
                return False

            ledger.append_event(
                terminal_id,
                turn_id,
                "PostToolUse",
                "skill_phase_transition",
                {"phase": to_state, "from_phase": from_phase},
            )
            state = dict(state)
            state["phase"] = to_state
            state["terminal_id"] = terminal_id
            state["turn_id"] = turn_id
            state["updated_at"] = time.time()
            _write_pending_state_file(terminal_id, state)
            return True
        except Exception:
            pass

    state = _read_pending_state_file(terminal_id)
    if not isinstance(state, dict):
        return False
    if turn_id and str(state.get("turn_id", "")) not in {"", turn_id}:
        return False

    from_phase = state.get("phase", _PHASE_PENDING)
    allowed = VALID_TRANSITIONS.get(from_phase, [])
    if to_state not in allowed:
        return False

    state["phase"] = to_state
    state["terminal_id"] = terminal_id
    state["turn_id"] = turn_id or str(state.get("turn_id", ""))
    state["updated_at"] = time.time()
    _write_pending_state_file(terminal_id, state)
    return True


def read_pending_state() -> dict | None:
    """Read current skill execution state from state file.

    Returns:
        State dict or None if no skill loaded
    """
    try:
        terminal_id, turn_id = _get_active_turn_scope()
        if not terminal_id:
            return None
        if turn_id:
            ledger = _get_ledger_module()
            snapshot = ledger.materialize_turn(terminal_id, turn_id)
            state = snapshot.get("skill_state")
            if isinstance(state, dict):
                return state
            file_state = _read_pending_state_file(terminal_id)
            if isinstance(file_state, dict) and str(file_state.get("turn_id", "")) == turn_id:
                return file_state
            return None
        return _read_pending_state_file(terminal_id)
    except Exception:
        terminal_id = detect_terminal_id()
        if terminal_id:
            return _read_pending_state_file(terminal_id)
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


def mark_first_command_validated() -> None:
    """Mark that the first command-level workflow check passed.

    Called by PreToolUse_skill_pattern_gate after validating the first
    substantive command matches the skillr's declared first-command pattern.
    Subsequent command calls skip the first-command check.
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
            "skill_first_command_validated",
            {"validated": True},
        )
    except Exception:
        pass


def update_workflow_stage(
    active_step: str = "",
    step_definition: str = "",
    done_criteria: list[str] | None = None,
    do_not_distract: list[str] | None = None,
    step_index: int | None = None,
    total_steps: int | None = None,
) -> None:
    """Update workflow stage fields for topic drift prevention.

    Called when skill workflow steps are defined or progress.
    This populates the workflow_stage fields that PreToolUse_skill_pattern_gate
    Layer 0.5 checks to prevent topic drift.

    Args:
        active_step: Current step being worked on
        step_definition: Description of current step
        done_criteria: List of completion criteria for current step
        do_not_distract: List of deferred items to avoid distracting from current step
        step_index: Current step number (0-indexed)
        total_steps: Total number of steps in workflow
    """
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id or not turn_id:
        return

    payload: dict[str, Any] = {"updated": True}
    if active_step:
        payload["active_step"] = active_step
    if step_definition:
        payload["step_definition"] = step_definition
    if done_criteria is not None:
        payload["done_criteria"] = done_criteria
    if do_not_distract is not None:
        payload["do_not_distract"] = do_not_distract
    if step_index is not None:
        payload["step_index"] = step_index
    if total_steps is not None:
        payload["total_steps"] = total_steps

    try:
        ledger = _get_ledger_module()
        ledger.append_event(
            terminal_id,
            turn_id,
            "PostToolUse",
            "skill_workflow_stage_update",
            payload,
        )
    except Exception:
        pass


def clear_state() -> None:
    """Clear current skill execution state for the active turn."""
    terminal_id, turn_id = _get_active_turn_scope()
    if not terminal_id:
        return
    try:
        if turn_id:
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
    _clear_pending_state_file(terminal_id)


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
        legacy_data.setdefault("required_phase_artifacts", [])
        legacy_data.setdefault("workflow_binding", "")
        legacy_data.setdefault("workflow_enforcement", "")
        legacy_data.setdefault("phase_recovery_mode", "")
        legacy_data.setdefault("user_override", "")
        legacy_data.setdefault("contract_type", "analysis")
        legacy_data.setdefault("output_enforcement", "")
        legacy_data.setdefault("final_output_schema", "")
        legacy_data.setdefault("required_markers", [])
        legacy_data.setdefault("required_sections", [])
        legacy_data.setdefault("completion_criteria", [])
        legacy_data.setdefault("enforcement_tier", "")

        # Write to new location
        new_state_file = _get_state_file()
        new_state_file.parent.mkdir(parents=True, exist_ok=True)
        new_state_file.write_text(json.dumps(legacy_data, indent=2))

        # Remove legacy file
        legacy_state.unlink()

    except (json.JSONDecodeError, OSError):
        pass


def cleanup_stale_state_files(stale_timeout: int | None = None) -> int:
    """Remove state directories for terminals that no longer exist.

    Scans P:\\\\\.claude/.state/skill_execution_* directories and removes
    those belonging to terminals that are no longer active.

    Args:
        stale_timeout: Seconds after which a state directory is considered stale.
            Defaults to DEFAULT_STALE_TIMEOUT (300 seconds).

    Returns:
        Number of directories removed.
    """
    if stale_timeout is None:
        stale_timeout = DEFAULT_STALE_TIMEOUT

    removed_count = 0
    current_terminal_id = detect_terminal_id()

    if not STATE_DIR.exists():
        return 0

    try:
        # Get all skill_execution_* directories
        for state_subdir in STATE_DIR.iterdir():
            if not state_subdir.is_dir():
                continue
            if not state_subdir.name.startswith("skill_execution_"):
                continue

            # Extract terminal_id from directory name
            dir_terminal_id = state_subdir.name.replace("skill_execution_", "")

            # Don't remove current terminal's state
            if dir_terminal_id == current_terminal_id:
                continue

            # Check if this terminal still exists (via ledger)
            try:
                ledger = _get_ledger_module()
                if ledger is not None and ledger.get_active_turn(dir_terminal_id) is not None:
                    continue
            except Exception:
                # If we can't determine activity, check file age as fallback
                pass

            # Check directory age
            try:
                dir_mtime = state_subdir.stat().st_mtime
                age_seconds = time.time() - dir_mtime
                if age_seconds < stale_timeout:
                    continue
            except OSError:
                pass

            # Remove stale directory
            try:
                import shutil
                shutil.rmtree(state_subdir)
                removed_count += 1
            except OSError:
                pass

    except OSError:
        pass

    return removed_count
