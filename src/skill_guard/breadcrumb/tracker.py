#!/usr/bin/env python3
"""
Breadcrumb Trail Tracker
========================

Workflow step verification system for skill execution.

This module implements the breadcrumb trail pattern:
1. Skills declare workflow_steps in SKILL.md frontmatter
2. Skill hooks call set_breadcrumb() as steps complete
3. Global hooks verify breadcrumb trail completion
4. Block or advise when trail is incomplete

State files are terminal-scoped for multi-terminal safety.
Automatic cleanup on SessionEnd and PreCompact prevents filesystem litter.

v2.0 CHANGES:
- Terminal-scoped only (no session_id - session_id changes during compaction)
- Automatic cleanup on SessionEnd (all trails for this terminal)
- Automatic cleanup on PreCompact (stale trails)
- Age-based cleanup for orphaned trails (>2 hours old)
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from skill_guard.breadcrumb import database, sqlite_backend

# Import SQLite backend
from skill_guard.breadcrumb.cache import BreadcrumbStateCache

# Import hybrid logging components
from skill_guard.breadcrumb.log import AppendOnlyBreadcrumbLog

# Import terminal detection from skill_guard utilities
from skill_guard.utils.terminal_detection import detect_terminal_id

try:
    import yaml
except ImportError:
    yaml = None  # pyyaml declared as optional dependency

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")
# Maximum age for breadcrumb trails (2 hours)
MAX_TRAIL_AGE_SECONDS = 7200

# Global cache instance (terminal-scoped keys for multi-terminal safety)
_cache = BreadcrumbStateCache()

HOOKS_LIB_DIR = Path("P:/.claude/hooks/__lib")

# Database path (uses existing diagnostics.db)
DB_PATH = database.DEFAULT_DB_PATH

# Track if database has been initialized
_db_initialized = False


def _ensure_database_initialized() -> bool:
    """Ensure database schema is initialized.

    Returns:
        True if database is available and initialized, False otherwise
    """
    global _db_initialized

    if _db_initialized:
        return True

    try:
        conn = database.get_connection(DB_PATH)
        if conn is None:
            return False

        database.initialize_schema(conn)
        _db_initialized = True
        return True

    except Exception:
        return False


def _append_ledger_event(event_type: str, payload: dict[str, Any]) -> None:
    """Write breadcrumb lifecycle events through the shared hook ledger."""
    terminal_id = detect_terminal_id()
    if not terminal_id:
        return

    try:
        if HOOKS_LIB_DIR.exists() and str(HOOKS_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_LIB_DIR))
        import hook_ledger  # type: ignore

        turn_id = hook_ledger.get_active_turn(terminal_id) or ""
        if not turn_id:
            return
        hook_ledger.append_event(
            terminal_id,
            str(turn_id),
            "Breadcrumb",
            event_type,
            payload,
        )
    except Exception:
        pass


# =============================================================================
# STATE MANAGEMENT
# =============================================================================


def _get_breadcrumb_dir() -> Path:
    """Get the breadcrumb state directory for this terminal."""
    terminal_id = detect_terminal_id()
    breadcrumb_dir = STATE_DIR / f"breadcrumbs_{terminal_id}"
    breadcrumb_dir.mkdir(parents=True, exist_ok=True)
    return breadcrumb_dir


def _get_breadcrumb_file(skill_name: str) -> Path:
    """Get the breadcrumb trail file for a skill.

    Args:
        skill_name: Name of the skill

    Returns:
        Path to breadcrumb state file

    Raises:
        ValueError: If skill_name contains path traversal characters (. or ..)
    """
    # Security: Block path traversal attempts
    if "." in skill_name or ".." in skill_name:
        raise ValueError(
            f"Invalid skill name '{skill_name}': contains path traversal characters. "
            "Skill names cannot contain '.' or '..' for security reasons."
        )

    skill_lower = skill_name.lower().replace("/", "_").replace(" ", "_")
    return _get_breadcrumb_dir() / f"breadcrumb_{skill_lower}.json"


def _load_workflow_steps(skill_name: str) -> list[dict]:
    """Load workflow_steps from a skill's SKILL.md frontmatter.

    Args:
        skill_name: Skill name (without slash)

    Returns:
        List of workflow step dicts with id, kind, optional, and status.
        Format: [{"id": str, "kind": str, "optional": bool}, ...]
    """
    steps: list[dict] = []
    defaults = {"kind": "execution", "optional": False}
    skill_dir = Path("P:/.claude/skills") / skill_name.lower()
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return steps

    if yaml is None:
        return steps

    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return steps
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return steps
        wf_steps = fm_data.get("workflow_steps", [])
        if isinstance(wf_steps, list):
            for s in wf_steps:
                if isinstance(s, str):
                    # String format: convert to dict with defaults
                    steps.append({"id": s, **defaults})
                elif isinstance(s, dict):
                    # Dict format: merge with defaults, preserve explicit values
                    normalized_step = {**defaults, **s}
                    # Ensure 'id' field exists
                    if "id" not in normalized_step:
                        normalized_step["id"] = str(s)
                    steps.append(normalized_step)
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "Failed to load workflow_steps for skill %s: %s. "
            "Returning empty steps list.",
            skill_name,
            str(e),
        )

    return steps


def initialize_breadcrumb_trail(skill_name: str, force: bool = False) -> None:
    """Initialize breadcrumb trail for a skill.

    Called when a skill is invoked. Loads workflow_steps from frontmatter
    and creates breadcrumb state file with all steps as "pending".

    Args:
        skill_name: Name of the skill being invoked
        force: If True, force fresh initialization even if trail exists for this terminal.
               Used for testing or when explicit re-initialization is needed.
    """
    skill_lower = skill_name.lower()

    # HYBRID LOGGING: Check if breadcrumb file already exists
    # This prevents overwriting manually-created trails in tests
    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    if breadcrumb_file.exists() and not force:
        try:
            existing_trail = json.loads(breadcrumb_file.read_text(encoding="utf-8"))
            # Verify terminal_id matches (multi-terminal safety)
            if existing_trail.get("terminal_id") == detect_terminal_id():
                # Load existing trail into cache and return early
                _cache.update_state(skill_lower, existing_trail)
                return
            # Terminal ID mismatch - stale file from different terminal, delete and recreate
            try:
                breadcrumb_file.unlink(missing_ok=True)
            except OSError:
                pass
        except (json.JSONDecodeError, OSError):
            pass

    # Load workflow steps from frontmatter
    workflow_steps = _load_workflow_steps(skill_lower)

    # If no workflow steps declared, don't track
    if not workflow_steps:
        return

    # Generate unique run_id for this skill invocation
    run_id = str(uuid.uuid4())

    # Convert workflow_steps list to steps dict with metadata
    steps = {}
    for step in workflow_steps:
        step_id = step["id"] if isinstance(step, dict) else step
        steps[step_id] = {
            "kind": step.get("kind", "execution") if isinstance(step, dict) else "execution",
            "optional": step.get("optional", False) if isinstance(step, dict) else False,
            "status": "pending",
            "evidence": {},
        }

    # Initialize breadcrumb trail (terminal-scoped only, not session-scoped)
    # CRITICAL: Only use terminal_id for multi-terminal safety
    # Session ID is global across terminals and changes during compaction
    trail = {
        "skill": skill_lower,
        "terminal_id": detect_terminal_id(),
        "run_id": run_id,
        "initialized_at": time.time(),
        "workflow_steps": workflow_steps,  # Keep for backward compatibility
        "steps": steps,  # New: steps dict with full metadata
        "completed_steps": [],
        "current_step": None,
        "last_updated": time.time(),
        "tool_count": 0,  # Track number of tools used (for MINIMAL level)
    }

    # Try SQLite backend first
    db_available = _ensure_database_initialized()
    if db_available:
        try:
            run_id = sqlite_backend.create_trail(
                db_path=DB_PATH,
                skill=skill_lower,
                terminal_id=detect_terminal_id(),
                workflow_steps=workflow_steps,
                steps=steps,
            )
            # Update trail with the generated run_id
            trail["run_id"] = run_id
        except Exception:
            # Fall back to file-based operations on error
            pass

    # ALWAYS: Write file for backward compatibility (even if SQLite succeeds)
    # This ensures tools that expect files can still work
    # HYBRID LOGGING: Append initialization event to log
    log = AppendOnlyBreadcrumbLog(skill_lower)
    log.append(
        {
            "event": "trail_initialized",
            "run_id": run_id,
            "workflow_steps": workflow_steps,
            "steps": steps,
        }
    )

    # HYBRID LOGGING: Update cache
    _cache.update_state(skill_lower, trail)

    # HYBRID LOGGING: Write breadcrumb file (backward compatibility snapshot)
    with open(breadcrumb_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(trail, indent=2))
        f.flush()
        os.fsync(f.fileno())
    _append_ledger_event(
        "breadcrumb_initialized",
        {
            "skill": skill_lower,
            "run_id": run_id,
            "workflow_steps": workflow_steps,
        },
    )


def set_breadcrumb(skill_name: str, step_name: str, evidence: dict[str, Any] | None = None) -> None:
    """Mark a workflow step as completed.

    Called by skill hooks as they complete workflow steps.

    Args:
        skill_name: Name of the skill
        step_name: Name of the completed step (must match workflow_steps)
        evidence: Optional evidence dict for verification (default: None)
    """
    skill_lower = skill_name.lower()

    # HYBRID LOGGING: Try to get from cache first (lazy loads from log if needed)
    trail = _cache.get_state(skill_lower)

    if not trail:
        # Trail not initialized, initialize first
        initialize_breadcrumb_trail(skill_lower)
        trail = _cache.get_state(skill_lower)
        if not trail:
            return  # No workflow steps declared

    # Validate step is in workflow_steps
    # Extract step IDs from workflow_steps list (supports both dict and string formats)
    workflow_step_ids = []
    for step in trail.get("workflow_steps", []):
        if isinstance(step, dict):
            workflow_step_ids.append(step["id"])
        else:
            workflow_step_ids.append(step)

    if step_name not in workflow_step_ids:
        # Invalid step name, ignore
        return

    # Add to completed_steps if not already there
    completed = trail.get("completed_steps", [])
    step_was_already_complete = step_name in completed

    if not step_was_already_complete:
        completed.append(step_name)
        trail["completed_steps"] = completed
        trail["current_step"] = step_name
        trail["last_updated"] = time.time()

    # Update step status and evidence in steps dict
    # NOTE: Evidence can be updated even if step was already complete
    if "steps" in trail and step_name in trail["steps"]:
        trail["steps"][step_name]["status"] = "done"
        if evidence is not None:
            trail["steps"][step_name]["evidence"] = evidence

    # Try SQLite backend first
    run_id = trail.get("run_id")
    if run_id and _db_initialized:
        try:
            sqlite_backend.update_trail(
                db_path=DB_PATH,
                run_id=run_id,
                completed_steps=completed,
                current_step=step_name,
                steps=trail["steps"],
            )
        except Exception:
            # Fall back to file-based operations on error
            pass

    # ALWAYS: Write file for backward compatibility (even if SQLite succeeds)
    # HYBRID LOGGING: Append to log (atomic write, no read-modify-write)
    log = AppendOnlyBreadcrumbLog(skill_lower)
    log.append(
        {
            "event": "step_complete",
            "step": step_name,
            "evidence": evidence,
        }
    )

    # HYBRID LOGGING: Update cache (in-memory, fast)
    _cache.update_state(skill_lower, trail)

    # HYBRID LOGGING: Write breadcrumb file (backward compatibility snapshot)
    # Note: This could be optimized to only write periodically, but keeping
    # for backward compatibility with existing systems that read JSON files
    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    with open(breadcrumb_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(trail, indent=2))
        f.flush()
        os.fsync(f.fileno())
    _append_ledger_event(
        "breadcrumb_step_complete",
        {
            "skill": skill_lower,
            "step": step_name,
            "completed_steps": completed,
            "evidence": evidence,
        },
    )


def _windows_safe_unlink(path: Path) -> None:
    """Delete a file with Windows handle release workaround.

    On Windows, Python 3.14 holds file handles open after context manager exit.
    This can prevent unlink() from actually deleting files. Applies gc.collect()
    + rename workaround to ensure file deletion.
    """
    import gc as gc_module
    import time as time_module

    for _ in range(3):
        gc_module.collect()
    if path.exists():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            time_module.sleep(0.05)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                tmp_name = str(path) + f".orphaned_{time_module.time_ns()}"
                try:
                    path.rename(tmp_name)
                except OSError:
                    pass


def get_breadcrumb_trail(skill_name: str) -> dict[str, Any] | None:
    """Get current breadcrumb trail for a skill.

    Verifies session isolation to prevent cross-terminal contamination.

    Args:
        skill_name: Name of the skill

    Returns:
        Trail dict or None if no trail exists or session mismatch
    """
    skill_lower = skill_name.lower()
    breadcrumb_file = _get_breadcrumb_file(skill_lower)

    # HYBRID LOGGING: Try cache first (lazy loads from log if needed)
    trail = _cache.get_state(skill_lower)

    # If cache returned state, verify it has terminal_id (authoritative field).
    # _load_from_log may reconstruct incomplete state from JSONL log (no terminal_id).
    # If terminal_id is missing, treat as cache miss and read from breadcrumb file.
    if trail and not trail.get("terminal_id"):
        # Cached state incomplete (no terminal_id) - read from authoritative file
        trail = None

    if not trail:
        # Cache miss or incomplete: read from authoritative breadcrumb file
        if not breadcrumb_file.exists():
            return None

        try:
            trail = json.loads(breadcrumb_file.read_text())

            # Verify session isolation (multi-terminal safety)
            if not verify_session_isolation(trail):
                # Remove stale trail from different session/terminal
                _windows_safe_unlink(breadcrumb_file)
                return None

            # Load into cache for next access (with complete state including terminal_id)
            _cache.update_state(skill_lower, trail)

        except (json.JSONDecodeError, OSError):
            return None

    # Cache HIT: Verify the file's terminal_id matches the cached terminal_id
    # to detect external modifications (e.g., another terminal editing the file)
    try:
        if breadcrumb_file.exists():
            file_trail = json.loads(breadcrumb_file.read_text())
            file_terminal_id = file_trail.get("terminal_id", "")
            cached_terminal_id = trail.get("terminal_id", "")
            # If file was modified externally with a different terminal_id, re-verify
            if file_terminal_id and file_terminal_id != cached_terminal_id:
                if not verify_session_isolation(file_trail):
                    _windows_safe_unlink(breadcrumb_file)
                    _cache.invalidate(skill_lower)
                    return None
    except (json.JSONDecodeError, OSError):
        pass

    # Verify session isolation on cached trail (multi-terminal safety)
    if not verify_session_isolation(trail):
        # Invalidate cache and remove stale file
        _cache.invalidate(skill_lower)
        _windows_safe_unlink(breadcrumb_file)
        return None

    return trail


def verify_breadcrumb_trail(skill_name: str) -> tuple[bool, str]:
    """Verify breadcrumb trail completion using tiered enforcement.

    Uses enforcement levels (MINIMAL/STANDARD/STRICT) to verify completion.

    Args:
        skill_name: Name of the skill

    Returns:
        (is_complete, message) tuple
    """
    from skill_guard.breadcrumb.enforcement import verify_with_enforcement

    trail = get_breadcrumb_trail(skill_name)

    # Calculate duration and tool count for enforcement levels
    duration_seconds = 0.0
    tool_count = 0

    if trail:
        # Calculate session duration
        initialized_at = trail.get("initialized_at", time.time())
        duration_seconds = time.time() - initialized_at

        # Get tool count (tracked in trail)
        tool_count = trail.get("tool_count", 0)

    # Use tiered enforcement verification
    return verify_with_enforcement(
        skill_name=skill_name,
        trail=trail,
        duration_seconds=duration_seconds,
        tool_count=tool_count,
    )


def clear_breadcrumb_trail(skill_name: str) -> None:
    """Clear breadcrumb trail for a skill.

    Called when skill execution is complete.

    Args:
        skill_name: Name of the skill
    """
    skill_lower = skill_name.lower()

    # Get trail to find run_id
    trail = _cache.get_state(skill_lower)
    run_id = trail.get("run_id") if trail else None

    # Try SQLite backend first
    if run_id and _db_initialized:
        try:
            sqlite_backend.delete_trail(DB_PATH, run_id)
        except Exception:
            # Fall back to file-based operations on error
            pass
        else:
            # SQLite delete succeeded - also delete file for complete cleanup
            _cache.invalidate(skill_lower)
            log = AppendOnlyBreadcrumbLog(skill_lower)
            log.clear()
            breadcrumb_file = _get_breadcrumb_file(skill_lower)
            _windows_safe_unlink(breadcrumb_file)
            _append_ledger_event(
                "breadcrumb_cleared",
                {"skill": skill_lower},
            )
            return  # Success - both SQLite and file cleaned up

    # FALLBACK: File-based operations (backward compatibility)
    # HYBRID LOGGING: Clear cache
    _cache.invalidate(skill_lower)

    # HYBRID LOGGING: Clear log
    log = AppendOnlyBreadcrumbLog(skill_lower)
    log.clear()

    # HYBRID LOGGING: Clear breadcrumb file (backward compatibility)
    breadcrumb_file = _get_breadcrumb_file(skill_lower)
    _windows_safe_unlink(breadcrumb_file)
    _append_ledger_event(
        "breadcrumb_cleared",
        {"skill": skill_lower},
    )


def clear_all_breadcrumb_trails() -> None:
    """Clear all breadcrumb trails for this terminal.

    Useful for cleanup or state reset.
    """
    breadcrumb_dir = _get_breadcrumb_dir()
    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        _windows_safe_unlink(file)


# =============================================================================
# CLEANUP PROTOCOL
# =============================================================================


def cleanup_session_breadcrumbs() -> int:
    """Clean up all breadcrumb trails for this terminal (SessionEnd hook).

    Called by SessionEnd hook to clean up trails when session terminates.
    This prevents stale breadcrumb trails from littering the filesystem.

    Returns:
        Number of trails cleaned up
    """
    current_terminal_id = detect_terminal_id()
    cleaned_count = 0

    # Try SQLite backend first
    if _db_initialized:
        try:
            cleaned_count = sqlite_backend.clear_terminal_trails(DB_PATH, current_terminal_id)
        except Exception:
            # Fall back to file-based operations on error
            cleaned_count = 0

    # Always also do file-based cleanup (hybrid logging: both SQLite AND files may exist)
    breadcrumb_dir = _get_breadcrumb_dir()

    if not breadcrumb_dir.exists():
        return cleaned_count

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())

            # Only clean up trails from this terminal (not session-scoped)
            trail_terminal = trail.get("terminal_id")

            if trail_terminal == current_terminal_id:
                # Extract skill name from file path (breadcrumb_<skill>.json -> <skill>)
                skill_name = file.stem.replace("breadcrumb_", "")

                # Invalidate cache before deleting file
                _cache.invalidate(skill_name)

                # Delete file (Windows-safe)
                _windows_safe_unlink(file)
                cleaned_count += 1

        except (json.JSONDecodeError, OSError):
            # Cleanup invalid files (Windows-safe)
            _windows_safe_unlink(file)
            cleaned_count += 1

    return cleaned_count


def cleanup_stale_breadcrumbs() -> int:
    """Clean up stale breadcrumb trails (PreCompact hook).

    Removes breadcrumb trails that are older than MAX_TRAIL_AGE_SECONDS.
    This prevents orphaned trails from accumulating over time.

    Called by PreCompact hook before session compaction occurs.

    Returns:
        Number of stale trails cleaned up
    """
    current_time = time.time()
    current_terminal_id = detect_terminal_id()
    total_cleaned = 0

    # Clean up SQLite trails
    if _db_initialized:
        try:
            # Get all trails for this terminal
            trails = sqlite_backend.get_active_trails(DB_PATH, current_terminal_id)

            cleaned_count = 0
            for trail in trails:
                # Check trail age
                initialized_at = trail.get("initialized_at", current_time)
                trail_age = current_time - initialized_at

                # Clean up stale trails
                if trail_age > MAX_TRAIL_AGE_SECONDS:
                    run_id = trail.get("run_id")
                    if run_id:
                        sqlite_backend.delete_trail(DB_PATH, run_id)
                        cleaned_count += 1

            total_cleaned += cleaned_count
        except Exception:
            # Continue to file-based cleanup on error
            pass

    # ALSO clean up file-based trails (backward compatibility & orphaned files)
    breadcrumb_dir = _get_breadcrumb_dir()

    if not breadcrumb_dir.exists():
        return total_cleaned

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())

            # Check trail age
            initialized_at = trail.get("initialized_at", current_time)
            trail_age = current_time - initialized_at

            # Clean up stale trails
            if trail_age > MAX_TRAIL_AGE_SECONDS:
                # Extract skill name from file path (breadcrumb_<skill>.json -> <skill>)
                skill_name = file.stem.replace("breadcrumb_", "")

                # Invalidate cache before deleting file
                _cache.invalidate(skill_name)

                # Delete file (Windows-safe)
                _windows_safe_unlink(file)
                total_cleaned += 1
                continue

            # Clean up trails from other terminals (cross-terminal contamination)
            trail_terminal = trail.get("terminal_id")
            if trail_terminal != current_terminal_id:
                # Extract skill name from file path
                skill_name = file.stem.replace("breadcrumb_", "")

                # Invalidate cache before deleting file
                _cache.invalidate(skill_name)

                # Delete file (Windows-safe)
                _windows_safe_unlink(file)
                total_cleaned += 1

        except (json.JSONDecodeError, OSError):
            # Cleanup invalid files (Windows-safe)
            _windows_safe_unlink(file)
            total_cleaned += 1

    # Clear cache to force reload
    _cache.clear_all()

    return total_cleaned


def verify_session_isolation(trail: dict[str, Any]) -> bool:
    """Verify that a breadcrumb trail belongs to this terminal.

    CRITICAL: Only checks terminal_id, not session_id.
    Session ID is global across terminals and changes during compaction.

    Args:
        trail: Trail dict to verify

    Returns:
        True if trail belongs to this terminal, False otherwise
    """
    current_terminal_id = detect_terminal_id()
    trail_terminal = trail.get("terminal_id")

    # Only check terminal_id (session_id changes during compaction)
    return trail_terminal == current_terminal_id


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_active_breadcrumb_trails() -> list[dict[str, Any]]:
    """Get all active breadcrumb trails for this terminal.

    Returns:
        List of trail dicts
    """
    current_terminal_id = detect_terminal_id()

    # Try SQLite backend first
    if _db_initialized:
        try:
            return sqlite_backend.get_active_trails(DB_PATH, current_terminal_id)
        except Exception:
            # Fall back to file-based operations on error
            pass

    # FALLBACK: File-based operations (backward compatibility)
    breadcrumb_dir = _get_breadcrumb_dir()
    trails = []

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            trail = json.loads(file.read_text())
            trails.append(trail)
        except (json.JSONDecodeError, OSError):
            pass

    return trails


def format_breadcrumb_status(trail: dict[str, Any]) -> str:
    """Format breadcrumb trail for display.

    Args:
        trail: Trail dict from get_breadcrumb_trail()

    Returns:
        Formatted status string
    """
    skill = trail.get("skill", "unknown")
    workflow_steps = trail.get("workflow_steps", [])
    completed_steps = trail.get("completed_steps", [])

    # Normalize workflow_steps to list of step IDs (handles both str and dict formats)
    workflow_step_ids = [step["id"] if isinstance(step, dict) else step for step in workflow_steps]

    status = f"Skill: {skill}\n"
    status += f"Workflow: {len(completed_steps)}/{len(workflow_step_ids)} steps complete\n"

    if completed_steps:
        status += f"Completed: {', '.join(completed_steps)}\n"

    missing = [step for step in workflow_step_ids if step not in completed_steps]
    if missing:
        status += f"Missing: {', '.join(missing)}\n"

    return status
