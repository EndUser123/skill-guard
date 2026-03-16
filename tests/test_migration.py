#!/usr/bin/env python3
"""
Tests for migration.py module

Tests the migration from JSONL/JSON files to SQLite database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Create a temporary state directory for testing."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path for testing."""
    return tmp_path / "test_breadcrumbs.db"


@pytest.fixture
def sample_jsonl_data(temp_state_dir: Path) -> dict[str, Any]:
    """Create sample JSONL log files for testing.

    Returns:
        Dict with terminal_id and skill names
    """
    terminal_id = "test_terminal_123"

    # Create terminal-scoped log directory
    log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create sample JSONL logs for two skills
    skills = {
        "code": [
            {
                "timestamp": 1234567890.123,
                "event": "trail_initialized",
                "skill": "code",
                "run_id": "run-001",
                "workflow_steps": ["analyze", "implement", "test"],
                "steps": {
                    "analyze": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                    "implement": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                    "test": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                },
            },
            {
                "timestamp": 1234567891.456,
                "event": "step_complete",
                "skill": "code",
                "step": "analyze",
                "evidence": {"files_read": 5},
            },
            {
                "timestamp": 1234567892.789,
                "event": "step_complete",
                "skill": "code",
                "step": "implement",
                "evidence": {"lines_written": 100},
            },
        ],
        "refactor": [
            {
                "timestamp": 1234567895.000,
                "event": "trail_initialized",
                "skill": "refactor",
                "run_id": "run-002",
                "workflow_steps": ["analyze", "refactor", "verify"],
                "steps": {
                    "analyze": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                    "refactor": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                    "verify": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                },
            },
        ],
    }

    # Write JSONL files
    for skill_name, entries in skills.items():
        log_file = log_dir / f"{skill_name}.jsonl"
        with open(log_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    return {"terminal_id": terminal_id, "skills": list(skills.keys())}


@pytest.fixture
def sample_json_state(temp_state_dir: Path) -> dict[str, Any]:
    """Create sample JSON state files for testing.

    Returns:
        Dict with terminal_id and skill names
    """
    terminal_id = "test_terminal_123"

    # Create terminal-scoped breadcrumb directory
    breadcrumb_dir = temp_state_dir / f"breadcrumbs_{terminal_id}"
    breadcrumb_dir.mkdir(parents=True, exist_ok=True)

    # Create sample JSON state files
    skills = {
        "code": {
            "skill": "code",
            "terminal_id": terminal_id,
            "run_id": "run-001",
            "initialized_at": 1234567890.123,
            "workflow_steps": ["analyze", "implement", "test"],
            "steps": {
                "analyze": {"kind": "execution", "optional": False, "status": "done", "evidence": {"files_read": 5}},
                "implement": {"kind": "execution", "optional": False, "status": "done", "evidence": {"lines_written": 100}},
                "test": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
            },
            "completed_steps": ["analyze", "implement"],
            "current_step": "implement",
            "last_updated": 1234567892.789,
            "tool_count": 2,
        },
        "refactor": {
            "skill": "refactor",
            "terminal_id": terminal_id,
            "run_id": "run-002",
            "initialized_at": 1234567895.000,
            "workflow_steps": ["analyze", "refactor", "verify"],
            "steps": {
                "analyze": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                "refactor": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
                "verify": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
            },
            "completed_steps": [],
            "current_step": None,
            "last_updated": 1234567895.000,
            "tool_count": 0,
        },
    }

    # Write JSON state files
    for skill_name, state in skills.items():
        state_file = breadcrumb_dir / f"breadcrumb_{skill_name}.json"
        state_file.write_text(json.dumps(state, indent=2))

    return {"terminal_id": terminal_id, "skills": list(skills.keys())}


@pytest.fixture
def initialized_database(temp_db_path: Path) -> sqlite3.Connection:
    """Create an initialized database with breadcrumb schema.

    Returns:
        SQLite connection with schema initialized
    """
    conn = sqlite3.connect(temp_db_path)

    # Create breadcrumb_trails table
    conn.execute("""
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
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_terminal
        ON breadcrumb_trails(terminal_id, skill)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_run_id
        ON breadcrumb_trails(run_id)
    """)

    # Create breadcrumb_events table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS breadcrumb_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trail_id INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            FOREIGN KEY (trail_id) REFERENCES breadcrumb_trails(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_events_trail_timestamp
        ON breadcrumb_events(trail_id, timestamp DESC)
    """)

    conn.commit()
    return conn


# =============================================================================
# TESTS: MIGRATION VALIDATION
# =============================================================================


class TestMigrationValidation:
    """Tests for migration validation functionality."""

    def test_validate_jsonl_files_valid(self, sample_jsonl_data: dict[str, Any], temp_state_dir: Path) -> None:
        """Test validation of valid JSONL files."""
        from skill_guard.breadcrumb.migration import validate_jsonl_files

        terminal_id = sample_jsonl_data["terminal_id"]
        log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_jsonl_files(terminal_id)

        assert is_valid
        assert len(errors) == 0

    def test_validate_jsonl_files_missing_dir(self, temp_state_dir: Path) -> None:
        """Test validation when log directory doesn't exist."""
        from skill_guard.breadcrumb.migration import validate_jsonl_files

        terminal_id = "nonexistent_terminal"

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_jsonl_files(terminal_id)

        # Missing directory is not an error (no data to migrate)
        assert is_valid
        assert len(errors) == 0

    def test_validate_jsonl_files_corrupted_data(self, temp_state_dir: Path) -> None:
        """Test validation of corrupted JSONL files."""
        from skill_guard.breadcrumb.migration import validate_jsonl_files

        terminal_id = "test_terminal_456"
        log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create corrupted JSONL file
        log_file = log_dir / "code.jsonl"
        log_file.write_text("invalid json content\n{also invalid}\n")

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_jsonl_files(terminal_id)

        assert not is_valid
        assert len(errors) > 0
        # Error message contains the filename and line number
        assert any("code.jsonl" in str(err) for err in errors)

    def test_validate_json_state_valid(self, sample_json_state: dict[str, Any], temp_state_dir: Path) -> None:
        """Test validation of valid JSON state files."""
        from skill_guard.breadcrumb.migration import validate_json_state

        terminal_id = sample_json_state["terminal_id"]

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_json_state(terminal_id)

        assert is_valid
        assert len(errors) == 0

    def test_validate_json_state_missing_dir(self, temp_state_dir: Path) -> None:
        """Test validation when state directory doesn't exist."""
        from skill_guard.breadcrumb.migration import validate_json_state

        terminal_id = "nonexistent_terminal"

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_json_state(terminal_id)

        # Missing directory is not an error (no data to migrate)
        assert is_valid
        assert len(errors) == 0

    def test_validate_json_state_corrupted_data(self, temp_state_dir: Path) -> None:
        """Test validation of corrupted JSON state files."""
        from skill_guard.breadcrumb.migration import validate_json_state

        terminal_id = "test_terminal_789"
        breadcrumb_dir = temp_state_dir / f"breadcrumbs_{terminal_id}"
        breadcrumb_dir.mkdir(parents=True, exist_ok=True)

        # Create corrupted JSON file
        state_file = breadcrumb_dir / "breadcrumb_code.json"
        state_file.write_text("invalid json content")

        # Mock the state directory
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            is_valid, errors = validate_json_state(terminal_id)

        assert not is_valid
        assert len(errors) > 0
        assert any("corrupted" in str(err).lower() or "invalid" in str(err).lower() for err in errors)


# =============================================================================
# TESTS: JSONL TO EVENTS MIGRATION
# =============================================================================


class TestJsonlMigration:
    """Tests for JSONL to breadcrumb_events migration."""

    def test_migrate_jsonl_to_events(
        self, sample_jsonl_data: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test migration of JSONL logs to breadcrumb_events table."""
        from skill_guard.breadcrumb.migration import migrate_jsonl_to_events

        terminal_id = sample_jsonl_data["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            # First, migrate trails to establish trail_id references
            # This would normally be done by migrate_json_state_to_trails
            # For this test, we'll create a dummy trail
            cursor = initialized_database.cursor()
            cursor.execute(
                """
                INSERT INTO breadcrumb_trails
                (skill, terminal_id, run_id, initialized_at, workflow_steps, steps, completed_steps, current_step, last_updated, tool_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                ("code", terminal_id, "run-001", 1234567890.123, '["analyze", "implement", "test"]', '{}', '[]', None, 1234567892.789, 0),
            )
            trail_id = cursor.lastrowid
            initialized_database.commit()

            # Migrate JSONL to events
            success = migrate_jsonl_to_events(terminal_id, temp_db_path)

        assert success

        # Verify events were migrated
        cursor = initialized_database.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_events WHERE trail_id = ?", (trail_id,))
        count = cursor.fetchone()[0]

        # Should have 3 events: trail_initialized + 2 step_complete
        assert count == 3

    def test_migrate_jsonl_to_events_no_files(
        self, temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test migration when no JSONL files exist."""
        from skill_guard.breadcrumb.migration import migrate_jsonl_to_events

        terminal_id = "nonexistent_terminal"

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            success = migrate_jsonl_to_events(terminal_id, temp_db_path)

        # No files to migrate is not a failure
        assert success

    def test_migrate_jsonl_preserves_data_integrity(
        self, sample_jsonl_data: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test that migration preserves data integrity."""
        from skill_guard.breadcrumb.migration import migrate_jsonl_to_events

        terminal_id = sample_jsonl_data["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            # Create dummy trail
            cursor = initialized_database.cursor()
            cursor.execute(
                """
                INSERT INTO breadcrumb_trails
                (skill, terminal_id, run_id, initialized_at, workflow_steps, steps, completed_steps, current_step, last_updated, tool_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                ("code", terminal_id, "run-001", 1234567890.123, '["analyze", "implement", "test"]', '{}', '[]', None, 1234567892.789, 0),
            )
            trail_id = cursor.lastrowid
            initialized_database.commit()

            # Migrate
            migrate_jsonl_to_events(terminal_id, temp_db_path)

        # Verify event data integrity
        cursor = initialized_database.cursor()
        cursor.execute(
            "SELECT event_type, event_data FROM breadcrumb_events WHERE trail_id = ? ORDER BY timestamp",
            (trail_id,),
        )
        events = cursor.fetchall()

        assert len(events) == 3
        assert events[0][0] == "trail_initialized"
        assert events[1][0] == "step_complete"
        assert events[2][0] == "step_complete"


# =============================================================================
# TESTS: JSON TO TRAILS MIGRATION
# =============================================================================


class TestJsonMigration:
    """Tests for JSON to breadcrumb_trails migration."""

    def test_migrate_json_state_to_trails(
        self, sample_json_state: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test migration of JSON state files to breadcrumb_trails table."""
        from skill_guard.breadcrumb.migration import migrate_json_state_to_trails

        terminal_id = sample_json_state["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            success = migrate_json_state_to_trails(terminal_id, temp_db_path)

        assert success

        # Verify trails were migrated
        cursor = initialized_database.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        count = cursor.fetchone()[0]

        # Should have 2 trails (code and refactor)
        assert count == 2

    def test_migrate_json_state_no_files(
        self, temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test migration when no JSON state files exist."""
        from skill_guard.breadcrumb.migration import migrate_json_state_to_trails

        terminal_id = "nonexistent_terminal"

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            success = migrate_json_state_to_trails(terminal_id, temp_db_path)

        # No files to migrate is not a failure
        assert success

    def test_migrate_json_preserves_trail_integrity(
        self, sample_json_state: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test that migration preserves trail data integrity."""
        from skill_guard.breadcrumb.migration import migrate_json_state_to_trails

        terminal_id = sample_json_state["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            migrate_json_state_to_trails(terminal_id, temp_db_path)

        # Verify trail data integrity
        cursor = initialized_database.cursor()
        cursor.execute("SELECT skill, run_id, completed_steps, tool_count FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        trails = cursor.fetchall()

        assert len(trails) == 2

        # Find code trail
        code_trail = next((t for t in trails if t[0] == "code"), None)
        assert code_trail is not None
        assert code_trail[1] == "run-001"
        assert json.loads(code_trail[2]) == ["analyze", "implement"]
        assert code_trail[3] == 2


# =============================================================================
# TESTS: TRANSACTIONAL MIGRATION
# =============================================================================


class TestTransactionalMigration:
    """Tests for transactional migration with rollback."""

    def test_migration_is_transactional(
        self, sample_jsonl_data: dict[str, Any], sample_json_state: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test that migration is all-or-nothing (transactional)."""
        from skill_guard.breadcrumb.migration import migrate_terminal

        terminal_id = sample_json_state["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            # This should succeed
            success = migrate_terminal(terminal_id, temp_db_path)

        assert success

        # Verify both trails and events were migrated
        cursor = initialized_database.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        trail_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM breadcrumb_events")
        event_count = cursor.fetchone()[0]

        assert trail_count == 2
        assert event_count == 4  # code has 3 events, refactor has 1

    def test_migration_rollback_on_error(self, temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path) -> None:
        """Test that migration rolls back on error."""
        from skill_guard.breadcrumb.migration import migrate_terminal

        terminal_id = "test_terminal_error"

        # Create corrupted data that will cause migration to fail
        log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "code.jsonl").write_text("corrupted data")

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            success = migrate_terminal(terminal_id, temp_db_path)

        # Migration should fail
        assert not success

        # Verify no partial data was migrated
        cursor = initialized_database.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        trail_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM breadcrumb_events")
        event_count = cursor.fetchone()[0]

        assert trail_count == 0
        assert event_count == 0

    def test_migration_validation_failure(self, temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path) -> None:
        """Test that validation failure prevents migration."""
        from skill_guard.breadcrumb.migration import migrate_terminal

        terminal_id = "test_terminal_validation"

        # Create invalid JSONL file
        log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "code.jsonl").write_text("invalid json\n")

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            success = migrate_terminal(terminal_id, temp_db_path)

        # Migration should fail due to validation
        assert not success


# =============================================================================
# TESTS: ROLLBACK
# =============================================================================


class TestRollback:
    """Tests for migration rollback functionality."""

    def test_rollback_migration(
        self, sample_jsonl_data: dict[str, Any], sample_json_state: dict[str, Any], temp_db_path: Path, initialized_database: sqlite3.Connection, temp_state_dir: Path
    ) -> None:
        """Test rolling back a migration."""
        from skill_guard.breadcrumb.migration import migrate_terminal, rollback_migration

        terminal_id = sample_json_state["terminal_id"]

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            # Migrate first
            migrate_terminal(terminal_id, temp_db_path)

            # Verify migration succeeded
            cursor = initialized_database.cursor()
            cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
            trail_count = cursor.fetchone()[0]
            assert trail_count == 2

            # Rollback
            rollback_success = rollback_migration(terminal_id, temp_db_path)

        assert rollback_success

        # Verify rollback removed migrated data
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", (terminal_id,))
        trail_count_after = cursor.fetchone()[0]

        assert trail_count_after == 0

    def test_rollback_nonexistent_migration(self, temp_db_path: Path, initialized_database: sqlite3.Connection) -> None:
        """Test rolling back a migration that doesn't exist."""
        from skill_guard.breadcrumb.migration import rollback_migration

        terminal_id = "nonexistent_terminal"

        # Rollback should succeed even if no data exists
        success = rollback_migration(terminal_id, temp_db_path)

        assert success


# =============================================================================
# TESTS: CLI INTERFACE
# =============================================================================


class TestCLI:
    """Tests for CLI interface."""

    def test_migrate_cli_command(self, sample_jsonl_data: dict[str, Any], sample_json_state: dict[str, Any], temp_db_path: Path, temp_state_dir: Path) -> None:
        """Test CLI migrate command."""
        from skill_guard.breadcrumb.migration import cli_migrate

        terminal_id = sample_json_state["terminal_id"]

        # Mock paths and terminal detection
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir), \
             patch("skill_guard.breadcrumb.migration.detect_terminal_id", return_value=terminal_id):

            # Call CLI command
            result = cli_migrate(db_path=str(temp_db_path), terminal_id=terminal_id)

        assert result == 0  # 0 = success

    def test_migrate_cli_command_validation_error(self, temp_db_path: Path, temp_state_dir: Path) -> None:
        """Test CLI migrate command with validation error."""
        from skill_guard.breadcrumb.migration import cli_migrate

        terminal_id = "test_terminal_cli_error"

        # Create invalid data
        log_dir = temp_state_dir / f"breadcrumb_logs_{terminal_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "code.jsonl").write_text("invalid json\n")

        # Mock paths and terminal detection
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir), \
             patch("skill_guard.breadcrumb.migration.detect_terminal_id", return_value=terminal_id):

            # Call CLI command
            result = cli_migrate(db_path=str(temp_db_path), terminal_id=terminal_id)

        assert result != 0  # Non-zero = failure

    def test_migrate_cli_all_terminals(
        self, sample_jsonl_data: dict[str, Any], sample_json_state: dict[str, Any], temp_db_path: Path, temp_state_dir: Path
    ) -> None:
        """Test CLI migrate command for all terminals."""
        from skill_guard.breadcrumb.migration import cli_migrate_all

        # Mock paths
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir):
            # Call CLI command
            result = cli_migrate_all(db_path=str(temp_db_path))

        assert result == 0  # 0 = success

    def test_rollback_cli_command(self, temp_db_path: Path, temp_state_dir: Path) -> None:
        """Test CLI rollback command."""
        from skill_guard.breadcrumb.migration import cli_rollback

        terminal_id = "test_terminal_rollback"

        # Mock paths and terminal detection
        with patch("skill_guard.breadcrumb.migration.STATE_DIR", temp_state_dir), \
             patch("skill_guard.breadcrumb.migration.detect_terminal_id", return_value=terminal_id):

            # Call CLI command
            result = cli_rollback(db_path=str(temp_db_path), terminal_id=terminal_id)

        assert result == 0  # 0 = success (even if no data to rollback)
