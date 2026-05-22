r"""Migration helpers for skill execution state.

Extracted from skill_execution_state.py (ARCH-003 refactor).
Provides legacy state migration and stale state cleanup.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

# Import state I/O operations
from skill_guard._state_io import STATE_DIR, detect_terminal_id, _get_state_file

# Import ledger for terminal activity check
from skill_guard._ledger_integration import _get_ledger_module

# Import phase constants
from skill_guard.phases import DEFAULT_STALE_TIMEOUT


def migrate_legacy_state() -> None:
    """Migrate state from old location to new terminal-isolated location.

    This handles backward compatibility with state files created
    before v3.2 terminal isolation.

    Call this function explicitly from hooks or scripts when needed.
    Migration is no longer automatic on import to avoid side effects.
    """
    legacy_state = STATE_DIR / "skill_execution_pending.json"
    if not legacy_state.exists():
        return

    try:
        legacy_data = json.loads(legacy_state.read_text())

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

        new_state_file = _get_state_file()
        new_state_file.parent.mkdir(parents=True, exist_ok=True)
        new_state_file.write_text(json.dumps(legacy_data, indent=2))

        legacy_state.unlink()

    except (json.JSONDecodeError, OSError):
        pass


def cleanup_stale_state_files(stale_timeout: int | None = None) -> int:
    """Remove state directories for terminals that no longer exist.

    Scans P:/.claude/.state/skill_execution_* directories and removes
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
        for state_subdir in STATE_DIR.iterdir():
            if not state_subdir.is_dir():
                continue
            if not state_subdir.name.startswith("skill_execution_"):
                continue

            dir_terminal_id = state_subdir.name.replace("skill_execution_", "")

            if dir_terminal_id == current_terminal_id:
                continue

            try:
                ledger = _get_ledger_module()
                if ledger is not None and ledger.get_active_turn(dir_terminal_id) is not None:
                    continue
            except Exception:
                pass

            try:
                dir_mtime = state_subdir.stat().st_mtime
                age_seconds = time.time() - dir_mtime
                if age_seconds < stale_timeout:
                    continue
            except OSError:
                pass

            try:
                shutil.rmtree(state_subdir)
                removed_count += 1
            except OSError:
                pass

    except OSError:
        pass

    return removed_count