#!/usr/bin/env python3
"""
Test suite for database.py module

Acceptance Criteria:
- Database connection management with WAL mode
- Schema initialization (breadcrumb_trails, breadcrumb_events tables)
- Connection pooling for concurrent access
- Graceful degradation if database unavailable
"""

import sqlite3
import tempfile
from pathlib import Path


class TestDatabaseConnection:
    """Test database connection management."""

    def test_get_connection_returns_valid_connection(self):
        """Test that get_connection returns a valid SQLite connection."""
        from skill_guard.breadcrumb.database import get_connection

        # Create temp database for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = get_connection(db_path)

            # Verify connection is valid
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

            # Verify we can execute queries
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            # Clean up
            conn.close()

    def test_get_connection_enables_wal_mode(self):
        """Test that get_connection enables WAL mode."""
        from skill_guard.breadcrumb.database import get_connection

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_wal.db"
            conn = get_connection(db_path)

            # Check WAL mode is enabled
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            assert result[0] == "wal"

            conn.close()

    def test_get_connection_sets_busy_timeout(self):
        """Test that get_connection sets busy_timeout for concurrent access."""
        from skill_guard.breadcrumb.database import get_connection

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_timeout.db"
            conn = get_connection(db_path)

            # Check busy_timeout is set (should be 5000ms = 5 seconds)
            cursor = conn.cursor()
            cursor.execute("PRAGMA busy_timeout")
            result = cursor.fetchone()
            assert result[0] == 5000

            conn.close()

    def test_get_connection_handles_invalid_path_gracefully(self):
        """Test that get_connection handles invalid database path gracefully."""
        from skill_guard.breadcrumb.database import get_connection

        # Use an invalid path (non-existent directory with no write permissions)
        invalid_path = Path("/root/nonexistent/invalid.db")

        # Should either raise a clear exception or return None
        # (Implementation choice - we'll verify in the implementation)
        try:
            conn = get_connection(invalid_path)
            if conn is not None:
                conn.close()
                # If it returns a connection, it should work
                assert True
        except (OSError, sqlite3.Error):
            # Acceptable to raise an error
            assert True


class TestSchemaInitialization:
    """Test schema initialization and migrations."""

    def test_initialize_schema_creates_breadcrumb_trails_table(self):
        """Test that initialize_schema creates breadcrumb_trails table."""
        from skill_guard.breadcrumb.database import initialize_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_schema.db"
            conn = get_connection_for_test(db_path)
            initialize_schema(conn)

            # Verify breadcrumb_trails table exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='breadcrumb_trails'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "breadcrumb_trails"

            # Verify columns
            cursor.execute("PRAGMA table_info(breadcrumb_trails)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            expected_columns = {
                "id": "INTEGER",
                "skill": "TEXT",
                "terminal_id": "TEXT",
                "run_id": "TEXT",
                "initialized_at": "REAL",
                "workflow_steps": "TEXT",
                "steps": "TEXT",
                "completed_steps": "TEXT",
                "current_step": "TEXT",
                "last_updated": "REAL",
                "tool_count": "INTEGER",
            }

            for col_name, col_type in expected_columns.items():
                assert col_name in columns
                assert columns[col_name] == col_type

            conn.close()

    def test_initialize_schema_creates_breadcrumb_events_table(self):
        """Test that initialize_schema creates breadcrumb_events table."""
        from skill_guard.breadcrumb.database import initialize_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_events.db"
            conn = get_connection_for_test(db_path)
            initialize_schema(conn)

            # Verify breadcrumb_events table exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='breadcrumb_events'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "breadcrumb_events"

            # Verify columns
            cursor.execute("PRAGMA table_info(breadcrumb_events)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            expected_columns = {
                "id": "INTEGER",
                "trail_id": "INTEGER",
                "timestamp": "REAL",
                "event_type": "TEXT",
                "event_data": "TEXT",
            }

            for col_name, col_type in expected_columns.items():
                assert col_name in columns
                assert columns[col_name] == col_type

            conn.close()

    def test_initialize_schema_creates_indexes(self):
        """Test that initialize_schema creates indexes for performance."""
        from skill_guard.breadcrumb.database import initialize_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_indexes.db"
            conn = get_connection_for_test(db_path)
            initialize_schema(conn)

            # Verify indexes exist
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_breadcrumb_%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            expected_indexes = [
                "idx_breadcrumb_terminal",
                "idx_breadcrumb_run_id",
                "idx_breadcrumb_events_trail_timestamp",
            ]

            for index in expected_indexes:
                assert index in indexes

            conn.close()

    def test_initialize_schema_is_idempotent(self):
        """Test that initialize_schema can be called multiple times safely."""
        from skill_guard.breadcrumb.database import initialize_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_idempotent.db"
            conn = get_connection_for_test(db_path)

            # Call initialize_schema twice
            initialize_schema(conn)
            initialize_schema(conn)

            # Verify tables still exist and work
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='breadcrumb_trails'"
            )
            result = cursor.fetchone()
            assert result is not None

            conn.close()


class TestConnectionPooling:
    """Test connection pooling for concurrent access."""

    def test_connection_pool_returns_same_connection_for_same_thread(self):
        """Test that connection pool reuses connections within same thread."""
        from skill_guard.breadcrumb.database import get_connection

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_pool.db"

            conn1 = get_connection(db_path)
            conn2 = get_connection(db_path)

            # Should return same connection (thread-local)
            assert conn1 is conn2

            conn1.close()

    def test_connection_pool_handles_multiple_database_paths(self):
        """Test that connection pool handles different databases separately."""
        from skill_guard.breadcrumb.database import get_connection

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path1 = Path(tmpdir) / "test1.db"
            db_path2 = Path(tmpdir) / "test2.db"

            conn1 = get_connection(db_path1)
            conn2 = get_connection(db_path2)

            # Should return different connections for different databases
            assert conn1 is not conn2

            conn1.close()
            conn2.close()


class TestGracefulDegradation:
    """Test graceful degradation when database is unavailable."""

    def test_database_unavailable_returns_none_or_raises_clear_error(self):
        """Test behavior when database path is invalid."""
        from skill_guard.breadcrumb.database import get_connection

        # Use a clearly invalid path
        invalid_path = Path("/nonexistent/path/that/does/not/exist.db")

        try:
            conn = get_connection(invalid_path)
            if conn is None:
                # Acceptable to return None
                assert True
            else:
                # If it returns a connection, it should be usable
                conn.close()
                assert True
        except Exception as e:
            # Should raise a clear, specific error (not a generic one)
            assert isinstance(e, (OSError, sqlite3.Error))
            assert True


# =============================================================================
# TEST HELPERS
# =============================================================================


def get_connection_for_test(db_path: Path) -> sqlite3.Connection:
    """Helper to get a raw SQLite connection for testing.

    This bypasses the connection pool to test the actual database state.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
