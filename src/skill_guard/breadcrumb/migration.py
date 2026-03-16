#!/usr/bin/env python3
"""
Breadcrumb Migration Module
===========================

Migrates breadcrumb trails from JSONL+JSON files to SQLite database.

This module provides:
- Migration from JSONL logs to breadcrumb_events table
- Migration from JSON state files to breadcrumb_trails table
- Validation before migration (file integrity)
- Transactional migration (all-or-nothing)
- Rollback capability
- CLI interface for manual migration

Migration is terminal-scoped for multi-terminal safety.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Import terminal detection
from skill_guard.utils.terminal_detection import detect_terminal_id

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")

# =============================================================================
# VALIDATION
# =============================================================================


def validate_jsonl_files(terminal_id: str) -> tuple[bool, list[str]]:
    """Validate JSONL log files for a terminal.

    Args:
        terminal_id: Terminal identifier

    Returns:
        (is_valid, errors) tuple
    """
    errors: list[str] = []
    log_dir = STATE_DIR / f"breadcrumb_logs_{terminal_id}"

    if not log_dir.exists():
        # No logs to validate is not an error
        return True, []

    # Check each JSONL file
    for log_file in log_dir.glob("*.jsonl"):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(f"{log_file.name}:{line_num}: {e}")
        except (OSError, IOError) as e:
            errors.append(f"{log_file.name}: {e}")

    return len(errors) == 0, errors


def validate_json_state(terminal_id: str) -> tuple[bool, list[str]]:
    """Validate JSON state files for a terminal.

    Args:
        terminal_id: Terminal identifier

    Returns:
        (is_valid, errors) tuple
    """
    errors: list[str] = []
    breadcrumb_dir = STATE_DIR / f"breadcrumbs_{terminal_id}"

    if not breadcrumb_dir.exists():
        # No state files to validate is not an error
        return True, []

    # Check each JSON state file
    for state_file in breadcrumb_dir.glob("breadcrumb_*.json"):
        try:
            content = state_file.read_text(encoding="utf-8")
            data = json.loads(content)

            # Validate required fields
            required_fields = ["skill", "terminal_id", "run_id", "initialized_at", "workflow_steps", "steps"]
            for field in required_fields:
                if field not in data:
                    errors.append(f"{state_file.name}: Missing required field '{field}'")

        except json.JSONDecodeError as e:
            errors.append(f"{state_file.name}: Invalid JSON - {e}")
        except (OSError, IOError) as e:
            errors.append(f"{state_file.name}: {e}")

    return len(errors) == 0, errors


# =============================================================================
# MIGRATION: JSONL TO EVENTS
# =============================================================================


def migrate_jsonl_to_events(terminal_id: str, db_path: str | Path) -> bool:
    """Migrate JSONL logs to breadcrumb_events table.

    Args:
        terminal_id: Terminal identifier
        db_path: Path to SQLite database

    Returns:
        True if migration succeeded, False otherwise
    """
    log_dir = STATE_DIR / f"breadcrumb_logs_{terminal_id}"

    if not log_dir.exists():
        # No logs to migrate
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all trails for this terminal
        cursor.execute("SELECT id, run_id, skill FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        trails = cursor.fetchall()

        # Build skill -> trail_id mapping
        skill_trail_map = {skill: trail_id for trail_id, run_id, skill in trails}

        # Migrate each JSONL file
        for log_file in log_dir.glob("*.jsonl"):
            skill_name = log_file.stem  # Remove .jsonl extension

            # Find the trail_id for this skill
            # Use the most recent trail (first one found)
            trail_id = skill_trail_map.get(skill_name)

            if not trail_id:
                # No trail found, skip this log file
                # (It will be migrated when trails are migrated)
                continue

            # Read and migrate log entries
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # Extract event data
                        timestamp = entry.get("timestamp", 0)
                        event_type = entry.get("event", "unknown")

                        # Remove metadata fields from event_data
                        event_data = {k: v for k, v in entry.items() if k not in ["timestamp", "skill", "event"]}

                        # Insert event
                        cursor.execute(
                            """
                            INSERT INTO breadcrumb_events (trail_id, timestamp, event_type, event_data)
                            VALUES (?, ?, ?, ?)
                        """,
                            (trail_id, timestamp, event_type, json.dumps(event_data)),
                        )

                    except (json.JSONDecodeError, KeyError):
                        # Skip malformed entries
                        continue

        conn.commit()
        conn.close()
        return True

    except (sqlite3.Error, OSError):
        # Clean up on error
        try:
            conn.close()
        except Exception:
            pass
        return False


# =============================================================================
# MIGRATION: JSON TO TRAILS
# =============================================================================


def migrate_json_state_to_trails(terminal_id: str, db_path: str | Path) -> bool:
    """Migrate JSON state files to breadcrumb_trails table.

    Args:
        terminal_id: Terminal identifier
        db_path: Path to SQLite database

    Returns:
        True if migration succeeded, False otherwise
    """
    breadcrumb_dir = STATE_DIR / f"breadcrumbs_{terminal_id}"

    if not breadcrumb_dir.exists():
        # No state files to migrate
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Migrate each JSON state file
        for state_file in breadcrumb_dir.glob("breadcrumb_*.json"):
            try:
                content = state_file.read_text(encoding="utf-8")
                trail = json.loads(content)

                # Extract fields
                skill = trail.get("skill", "")
                run_id = trail.get("run_id", "")
                initialized_at = trail.get("initialized_at", 0)
                workflow_steps = json.dumps(trail.get("workflow_steps", []))
                steps = json.dumps(trail.get("steps", {}))
                completed_steps = json.dumps(trail.get("completed_steps", []))
                current_step = trail.get("current_step")
                last_updated = trail.get("last_updated", 0)
                tool_count = trail.get("tool_count", 0)

                # Insert trail
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO breadcrumb_trails
                    (skill, terminal_id, run_id, initialized_at, workflow_steps, steps, completed_steps, current_step, last_updated, tool_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (skill, terminal_id, run_id, initialized_at, workflow_steps, steps, completed_steps, current_step, last_updated, tool_count),
                )

            except (json.JSONDecodeError, KeyError, OSError):
                # Skip malformed files
                continue

        conn.commit()
        conn.close()
        return True

    except (sqlite3.Error, OSError):
        # Clean up on error
        try:
            conn.close()
        except Exception:
            pass
        return False


# =============================================================================
# TRANSACTIONAL MIGRATION
# =============================================================================


def _ensure_schema(db_path: str | Path) -> bool:
    """Ensure database schema exists.

    Args:
        db_path: Path to SQLite database

    Returns:
        True if schema exists or was created, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create breadcrumb_trails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breadcrumb_trails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill TEXT NOT NULL,
                terminal_id TEXT NOT NULL,
                run_id TEXT NOT NULL UNIQUE,
                initialized_at REAL NOT NULL,
                workflow_steps TEXT NOT NULL,
                steps TEXT NOT NULL,
                completed_steps TEXT NOT NULL,
                current_step TEXT,
                last_updated REAL NOT NULL,
                tool_count INTEGER DEFAULT 0
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_breadcrumb_terminal
            ON breadcrumb_trails(terminal_id, skill)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_breadcrumb_run_id
            ON breadcrumb_trails(run_id)
        """)

        # Create breadcrumb_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breadcrumb_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trail_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                FOREIGN KEY (trail_id) REFERENCES breadcrumb_trails(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_breadcrumb_events_trail_timestamp
            ON breadcrumb_events(trail_id, timestamp DESC)
        """)

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error:
        try:
            conn.close()
        except Exception:
            pass
        return False


def migrate_terminal(terminal_id: str, db_path: str | Path) -> bool:
    """Migrate all breadcrumb data for a terminal (transactional).

    Migrates both JSON state files and JSONL logs in a transaction.
    If either migration fails, rolls back all changes.

    Args:
        terminal_id: Terminal identifier
        db_path: Path to SQLite database

    Returns:
        True if migration succeeded, False otherwise
    """
    # Ensure schema exists
    if not _ensure_schema(db_path):
        return False

    # Validate first
    jsonl_valid, jsonl_errors = validate_jsonl_files(terminal_id)
    json_valid, json_errors = validate_json_state(terminal_id)

    if not jsonl_valid or not json_valid:
        # Validation failed
        return False

    # Migrate state files first (to establish trail IDs)
    if not migrate_json_state_to_trails(terminal_id, db_path):
        return False

    # Then migrate events
    if not migrate_jsonl_to_events(terminal_id, db_path):
        # Rollback trails on failure
        rollback_migration(terminal_id, db_path)
        return False

    return True


def migrate_all_terminals(db_path: str | Path) -> tuple[int, int]:
    """Migrate all terminals.

    Args:
        db_path: Path to SQLite database

    Returns:
        (success_count, failure_count) tuple
    """
    success_count = 0
    failure_count = 0

    # Find all terminal directories
    for log_dir in STATE_DIR.glob("breadcrumb_logs_*"):
        terminal_id = log_dir.name.replace("breadcrumb_logs_", "")

        if migrate_terminal(terminal_id, db_path):
            success_count += 1
        else:
            failure_count += 1

    # Also check breadcrumb directories that might not have logs
    for breadcrumb_dir in STATE_DIR.glob("breadcrumbs_*"):
        terminal_id = breadcrumb_dir.name.replace("breadcrumbs_", "")

        # Skip if already processed
        log_dir = STATE_DIR / f"breadcrumb_logs_{terminal_id}"
        if log_dir.exists():
            continue

        if migrate_terminal(terminal_id, db_path):
            success_count += 1
        else:
            failure_count += 1

    return success_count, failure_count


# =============================================================================
# ROLLBACK
# =============================================================================


def rollback_migration(terminal_id: str, db_path: str | Path) -> bool:
    """Rollback migration for a terminal.

    Removes all migrated data from the database.

    Args:
        terminal_id: Terminal identifier
        db_path: Path to SQLite database

    Returns:
        True if rollback succeeded, False otherwise
    """
    # If database doesn't exist, nothing to rollback
    if not Path(db_path).exists():
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Delete all events for trails belonging to this terminal
        cursor.execute(
            """
            DELETE FROM breadcrumb_events
            WHERE trail_id IN (
                SELECT id FROM breadcrumb_trails WHERE terminal_id = ?
            )
        """,
            (terminal_id,),
        )

        # Delete all trails for this terminal
        cursor.execute("DELETE FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error:
        try:
            conn.close()
        except Exception:
            pass
        return False


# =============================================================================
# CLI INTERFACE
# =============================================================================


def cli_migrate(db_path: str, terminal_id: str | None = None) -> int:
    """CLI command to migrate breadcrumb data.

    Args:
        db_path: Path to SQLite database
        terminal_id: Terminal ID to migrate (None for current terminal)

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    if terminal_id is None:
        terminal_id = detect_terminal_id()

    if not terminal_id:
        print("Error: Could not detect terminal ID", file=sys.stderr)
        return 1

    print(f"Migrating breadcrumb data for terminal: {terminal_id}")

    if migrate_terminal(terminal_id, db_path):
        print("Migration completed successfully")
        return 0
    else:
        print("Migration failed", file=sys.stderr)
        return 1


def cli_migrate_all(db_path: str) -> int:
    """CLI command to migrate all terminals.

    Args:
        db_path: Path to SQLite database

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print("Migrating breadcrumb data for all terminals...")

    success_count, failure_count = migrate_all_terminals(db_path)

    print(f"Migration completed: {success_count} succeeded, {failure_count} failed")

    return 0 if failure_count == 0 else 1


def cli_rollback(db_path: str, terminal_id: str | None = None) -> int:
    """CLI command to rollback migration.

    Args:
        db_path: Path to SQLite database
        terminal_id: Terminal ID to rollback (None for current terminal)

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    if terminal_id is None:
        terminal_id = detect_terminal_id()

    if not terminal_id:
        print("Error: Could not detect terminal ID", file=sys.stderr)
        return 1

    print(f"Rolling back migration for terminal: {terminal_id}")

    if rollback_migration(terminal_id, db_path):
        print("Rollback completed successfully")
        return 0
    else:
        print("Rollback failed", file=sys.stderr)
        return 1


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate breadcrumb trails to SQLite database")
    parser.add_argument("--db-path", default="P:/.claude/diagnostics.db", help="Path to SQLite database")
    parser.add_argument("--terminal", help="Terminal ID (default: auto-detect)")
    parser.add_argument("--all", action="store_true", help="Migrate all terminals")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")

    args = parser.parse_args()

    if args.rollback:
        sys.exit(cli_rollback(args.db_path, args.terminal))
    elif args.all:
        sys.exit(cli_migrate_all(args.db_path))
    else:
        sys.exit(cli_migrate(args.db_path, args.terminal))
