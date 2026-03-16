#!/usr/bin/env python3
"""
Tests for SQLite Backend for Breadcrumb Trails
===============================================

Tests the sqlite_backend.py module which provides SQLite-based breadcrumb operations.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path for testing."""
    return tmp_path / "test_breadcrumbs.db"


@pytest.fixture
def mock_terminal_id() -> str:
    """Mock terminal ID for testing."""
    # Note: database.py doesn't use detect_terminal_id anymore
    # Tests pass terminal_id directly to functions
    return "test-terminal-123"


@pytest.fixture
def sample_trail() -> dict[str, Any]:
    """Sample breadcrumb trail for testing."""
    return {
        "skill": "test-skill",
        "terminal_id": "test-terminal-123",
        "run_id": "test-run-456",
        "initialized_at": 1234567890.0,
        "workflow_steps": [
            {"id": "step1", "kind": "execution", "optional": False},
            {"id": "step2", "kind": "execution", "optional": False},
            {"id": "step3", "kind": "verification", "optional": True},
        ],
        "steps": {
            "step1": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
            "step2": {"kind": "execution", "optional": False, "status": "pending", "evidence": {}},
            "step3": {"kind": "verification", "optional": True, "status": "pending", "evidence": {}},
        },
        "completed_steps": [],
        "current_step": None,
        "last_updated": 1234567890.0,
        "tool_count": 0,
    }


# =============================================================================
# DATABASE MODULE TESTS (TASK-001 PREREQUISITE)
# =============================================================================


class TestDatabaseModule:
    """Test database.py module (TASK-001 prerequisite)."""

    def test_database_initialization(self, temp_db_path: Path, mock_terminal_id: str) -> None:
        """Test database can be initialized with schema."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema

        # Get connection and initialize schema
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Verify database file exists
        assert temp_db_path.exists()

        # Verify tables exist
        cursor = conn.cursor()

        # Check breadcrumb_trails table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='breadcrumb_trails'"
        )
        assert cursor.fetchone() is not None

        # Check breadcrumb_events table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='breadcrumb_events'"
        )
        assert cursor.fetchone() is not None

        # Check indexes
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_breadcrumb_terminal'"
        )
        assert cursor.fetchone() is not None

    def test_wal_mode_enabled(self, temp_db_path: Path) -> None:
        """Test WAL mode is enabled for better concurrency."""
        from skill_guard.breadcrumb.database import get_connection

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")

        cursor = conn.cursor()

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        assert result is not None
        assert result[0].lower() == "wal"


# =============================================================================
# SQLITE BACKEND TESTS (TASK-002)
# =============================================================================


class TestSQLiteBackend:
    """Test sqlite_backend.py module."""

    def test_create_trail(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test creating a new breadcrumb trail."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail

        # Initialize database
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Verify run_id is returned
        assert run_id is not None
        assert isinstance(run_id, str)

        # Verify trail was created in database
        from skill_guard.breadcrumb.database import get_connection

        conn = get_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None

        # Don't close conn - connection pooling manages lifecycle

    def test_update_trail(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test updating an existing breadcrumb trail."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Initialize database
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Update trail
        updated_trail = sample_trail.copy()
        updated_trail["run_id"] = run_id
        updated_trail["completed_steps"] = ["step1"]
        updated_trail["current_step"] = "step1"
        updated_trail["last_updated"] = time.time()

        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=updated_trail["completed_steps"],
            current_step=updated_trail["current_step"],
            steps=updated_trail["steps"],
        )

        # Verify update
        from skill_guard.breadcrumb.database import get_connection

        conn = get_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT completed_steps, current_step FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None

        completed_steps_json, current_step = row
        completed_steps = json.loads(completed_steps_json)

        assert completed_steps == ["step1"]
        assert current_step == "step1"

        conn.close()

    def test_append_event(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test appending an event to breadcrumb events table."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import append_event, create_trail

        # Initialize database
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Get trail_id from database
        from skill_guard.breadcrumb.database import get_connection

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None
        trail_id = row[0]
        # Don't close conn - connection pooling manages lifecycle

        # Append event
        append_event(
            db_path=temp_db_path,
            trail_id=trail_id,
            event_type="step_complete",
            event_data={"step": "step1", "evidence": {"test": "data"}},
        )

        # Verify event was appended
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT event_type, event_data FROM breadcrumb_events WHERE trail_id = ?",
            (trail_id,),
        )
        row = cursor.fetchone()
        assert row is not None

        event_type, event_data_json = row
        event_data = json.loads(event_data_json)

        assert event_type == "step_complete"
        assert event_data["step"] == "step1"
        assert event_data["evidence"]["test"] == "data"

        conn.close()

    def test_get_active_trails(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test getting active trails for a terminal."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        # Initialize database
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create trails for different terminals
        run_id1 = create_trail(
            db_path=temp_db_path,
            skill="skill1",
            terminal_id="terminal-1",
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        run_id2 = create_trail(
            db_path=temp_db_path,
            skill="skill2",
            terminal_id="terminal-1",
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Create trail for different terminal (should not be returned)
        run_id3 = create_trail(
            db_path=temp_db_path,
            skill="skill3",
            terminal_id="terminal-2",
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Get active trails for terminal-1
        trails = get_active_trails(db_path=temp_db_path, terminal_id="terminal-1")

        # Verify only terminal-1 trails are returned
        assert len(trails) == 2
        run_ids = [trail["run_id"] for trail in trails]
        assert run_id1 in run_ids
        assert run_id2 in run_ids
        assert run_id3 not in run_ids

    def test_cache_integration(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test cache integration with SQLite backend."""
        from skill_guard.breadcrumb.cache import BreadcrumbStateCache
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Initialize database
        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create cache instance
        cache = BreadcrumbStateCache()

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Update trail and cache
        updated_trail = sample_trail.copy()
        updated_trail["run_id"] = run_id
        updated_trail["completed_steps"] = ["step1"]
        updated_trail["current_step"] = "step1"
        updated_trail["last_updated"] = time.time()

        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=updated_trail["completed_steps"],
            current_step=updated_trail["current_step"],
            steps=updated_trail["steps"],
        )

        # Update cache
        cache.update_state(sample_trail["skill"], updated_trail)

        # Verify cache has the updated state
        cached_state = cache.get_state(sample_trail["skill"])
        assert cached_state is not None
        assert cached_state["completed_steps"] == ["step1"]
        assert cached_state["current_step"] == "step1"


# =============================================================================
# API COMPATIBILITY TESTS
# =============================================================================


class TestAPICompatibility:
    """Test SQLite backend API compatibility with existing tracker.py."""

    def test_create_trail_signature(self) -> None:
        """Test create_trail has correct signature."""
        import inspect

        from skill_guard.breadcrumb.sqlite_backend import create_trail
        sig = inspect.signature(create_trail)

        # Required parameters
        required_params = ["db_path", "skill", "terminal_id", "workflow_steps", "steps"]
        for param in required_params:
            assert param in sig.parameters

    def test_update_trail_signature(self) -> None:
        """Test update_trail has correct signature."""
        import inspect

        from skill_guard.breadcrumb.sqlite_backend import update_trail
        sig = inspect.signature(update_trail)

        # Required parameters
        required_params = ["db_path", "run_id", "completed_steps", "current_step", "steps"]
        for param in required_params:
            assert param in sig.parameters

    def test_append_event_signature(self) -> None:
        """Test append_event has correct signature."""
        import inspect

        from skill_guard.breadcrumb.sqlite_backend import append_event
        sig = inspect.signature(append_event)

        # Required parameters
        required_params = ["db_path", "trail_id", "event_type", "event_data"]
        for param in required_params:
            assert param in sig.parameters

    def test_get_active_trails_signature(self) -> None:
        """Test get_active_trails has correct signature."""
        import inspect

        from skill_guard.breadcrumb.sqlite_backend import get_active_trails
        sig = inspect.signature(get_active_trails)

        # Required parameters
        required_params = ["db_path", "terminal_id"]
        for param in required_params:
            assert param in sig.parameters


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Test performance requirements."""

    def test_create_trail_performance(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test create_trail completes in < 50ms."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        start = time.time()
        create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"create_trail took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_update_trail_performance(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test update_trail completes in < 50ms."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        start = time.time()
        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["step1"],
            current_step="step1",
            steps=sample_trail["steps"],
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"update_trail took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_append_event_performance(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test append_event completes in < 50ms."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import append_event, create_trail

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        run_id = create_trail(
            db_path=temp_db_path,
            skill=sample_trail["skill"],
            terminal_id=sample_trail["terminal_id"],
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Get trail_id
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None
        trail_id = row[0]
        # Don't close conn - connection pooling manages lifecycle

        start = time.time()
        append_event(
            db_path=temp_db_path,
            trail_id=trail_id,
            event_type="step_complete",
            event_data={"step": "step1"},
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"append_event took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_get_active_trails_performance(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test get_active_trails completes in < 50ms."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create multiple trails
        for i in range(10):
            create_trail(
                db_path=temp_db_path,
                skill=f"skill{i}",
                terminal_id="terminal-1",
                workflow_steps=sample_trail["workflow_steps"],
                steps=sample_trail["steps"],
            )

        start = time.time()
        trails = get_active_trails(db_path=temp_db_path, terminal_id="terminal-1")
        elapsed_ms = (time.time() - start) * 1000

        assert len(trails) == 10
        assert elapsed_ms < 50, f"get_active_trails took {elapsed_ms:.2f}ms, expected < 50ms"


# =============================================================================
# TERMINAL ISOLATION TESTS
# =============================================================================


class TestTerminalIsolation:
    """Test terminal-scoped queries maintain isolation."""

    def test_terminal_isolation(self, temp_db_path: Path, sample_trail: dict[str, Any]) -> None:
        """Test trails from different terminals are isolated."""
        from skill_guard.breadcrumb.database import get_connection, initialize_schema
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        conn = get_connection(temp_db_path)
        if conn is None:
            pytest.skip("Database unavailable")
        initialize_schema(conn)

        # Create trails for different terminals
        run_id1 = create_trail(
            db_path=temp_db_path,
            skill="skill1",
            terminal_id="terminal-1",
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        run_id2 = create_trail(
            db_path=temp_db_path,
            skill="skill2",
            terminal_id="terminal-2",
            workflow_steps=sample_trail["workflow_steps"],
            steps=sample_trail["steps"],
        )

        # Get active trails for terminal-1
        trails1 = get_active_trails(db_path=temp_db_path, terminal_id="terminal-1")
        run_ids1 = [trail["run_id"] for trail in trails1]

        # Get active trails for terminal-2
        trails2 = get_active_trails(db_path=temp_db_path, terminal_id="terminal-2")
        run_ids2 = [trail["run_id"] for trail in trails2]

        # Verify isolation
        assert run_id1 in run_ids1
        assert run_id1 not in run_ids2
        assert run_id2 in run_ids2
        assert run_id2 not in run_ids1
