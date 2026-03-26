#!/usr/bin/env python3
"""
Append-Only Breadcrumb Log
==========================

JSONL-based append-only log for breadcrumb trail audit trail.

Each log entry is a complete JSON object written atomically to a line.
This provides:
- Audit trail: All historical changes preserved
- Write efficiency: Append-only, no read-modify-write
- Crash safety: Partial writes don't corrupt existing data
- Terminal isolation: Logs scoped to terminal_id

JSONL Format:
{"timestamp": 1234567890.123, "event": "step_complete", "step": "analyze", "skill": "code"}
{"timestamp": 1234567891.456, "event": "step_complete", "step": "refactor", "skill": "code"}
...
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from skill_guard.utils.terminal_detection import detect_terminal_id

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")

# Maximum log file size before rotation (1 MB)
MAX_LOG_SIZE_BYTES = 1024 * 1024


# =============================================================================
# PATH MANAGEMENT
# =============================================================================


def _get_log_dir() -> Path:
    """Get the breadcrumb log directory for this terminal.

    Returns:
        Path to terminal-scoped log directory
    """
    terminal_id = detect_terminal_id()
    log_dir = STATE_DIR / f"breadcrumb_logs_{terminal_id}"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_log_file(skill_name: str) -> Path:
    """Get the append-only log file for a skill.

    Args:
        skill_name: Name of the skill

    Returns:
        Path to JSONL log file

    Raises:
        ValueError: If skill_name contains path traversal characters
    """
    # Security: Block path traversal attempts
    if "." in skill_name or ".." in skill_name:
        raise ValueError(
            f"Invalid skill name '{skill_name}': contains path traversal characters. "
            "Skill names cannot contain '.' or '..' for security reasons."
        )

    skill_lower = skill_name.lower().replace("/", "_").replace(" ", "_")
    return _get_log_dir() / f"{skill_lower}.jsonl"


# =============================================================================
# APPEND-ONLY LOG
# =============================================================================


class AppendOnlyBreadcrumbLog:
    """Append-only log for breadcrumb trail audit trail.

    Provides:
    - append(): Add new log entries (atomic writes)
    - replay(): Reconstruct state from log entries
    - Terminal-scoped paths for multi-terminal safety
    - Automatic log rotation when file size exceeds threshold

    Example:
        >>> log = AppendOnlyBreadcrumbLog("code")
        >>> log.append({"event": "step_complete", "step": "analyze"})
        >>> log.append({"event": "step_complete", "step": "refactor"})
        >>> entries = list(log.replay())
    """

    def __init__(self, skill_name: str) -> None:
        """Initialize append-only log for a skill.

        Args:
            skill_name: Name of the skill
        """
        self.skill_name = skill_name.lower()
        self.log_file = _get_log_file(skill_name)

    def append(self, entry: dict[str, Any]) -> None:
        """Append a log entry (atomic write).

        Args:
            entry: Log entry dict (will be augmented with timestamp and skill)

        Raises:
            ValueError: If entry is not a dict
            OSError: If write fails (disk full, permissions, etc.)
        """
        if not isinstance(entry, dict):
            raise ValueError(f"Log entry must be dict, got {type(entry)}")

        # Augment entry with metadata
        log_entry = {
            "timestamp": time.time(),
            "skill": self.skill_name,
            **entry,
        }

        # Convert to JSON and append with newline
        log_line = json.dumps(log_entry) + "\n"

        # Check if rotation needed
        if self.log_file.exists():
            if self.log_file.stat().st_size >= MAX_LOG_SIZE_BYTES:
                self._rotate_log()

        # Atomic append (open in append mode, write, close immediately)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
            f.flush()  # Ensure data is written to disk

    def replay(self) -> list[dict[str, Any]]:
        """Replay log entries from file (newest first).

        Returns:
            List of log entry dicts (newest to oldest)

        Note:
            Returns empty list if log file doesn't exist or is corrupted.
            Skips malformed lines rather than failing.
        """
        if not self.log_file.exists():
            return []

        entries = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        except (OSError, IOError):
            # Return empty list on read errors
            return []

        # Return newest first (reverse chronological)
        return list(reversed(entries))

    def _rotate_log(self) -> None:
        """Rotate log file when size exceeds threshold.

        Archives current log with timestamp and creates new empty log.

        Archive format: {skill_name}_{timestamp}.jsonl
        """
        if not self.log_file.exists():
            return

        # Create archive filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archive_file = self.log_file.parent / f"{self.log_file.stem}_{timestamp}.jsonl"

        # Rename current log to archive
        try:
            self.log_file.rename(archive_file)
        except OSError:
            # If rename fails (e.g., concurrent access), just append to current
            pass

    def clear(self) -> None:
        """Clear all log entries (remove log file).

        Warning:
            This permanently deletes the audit trail. Use with caution.
        """
        self.log_file.unlink(missing_ok=True)


# =============================================================================
# LOG DIRECTORY CLEANUP
# =============================================================================

import time as time_module


def cleanup_old_log_dirs(age_days: int = 7) -> dict[str, list[str]]:
    """Remove breadcrumb log directories older than age_days.

    Opportunistic cleanup prevents unbounded accumulation of orphaned log directories
    from past terminal sessions (e.g. fallback_term_* IDs).

    Args:
        age_days: Remove directories older than this many days. Defaults to 7.

    Returns:
        Dict with 'removed' (list of removed dir paths) and 'errors' (list of error messages).
    """
    cutoff = time_module.time() - (age_days * 24 * 3600)
    removed: list[str] = []
    errors: list[str] = []

    if not STATE_DIR.exists():
        return {"removed": removed, "errors": errors}

    for log_dir in STATE_DIR.iterdir():
        if not (log_dir.is_dir() and log_dir.name.startswith("breadcrumb_logs_")):
            continue
        try:
            mtime = log_dir.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            try:
                import shutil

                shutil.rmtree(log_dir)
                removed.append(str(log_dir))
            except OSError as e:
                errors.append(f"{log_dir}: {e}")

    return {"removed": removed, "errors": errors}
