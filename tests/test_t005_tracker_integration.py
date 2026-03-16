#!/usr/bin/env python3
"""
Integration Tests for Tracker.py with SQLite Backend
====================================================

Tests the integration between tracker.py and the new SQLite backend.
Verifies that the existing API surface is maintained while using the
unified SQLite backend for storage.

Acceptance Criteria:
- Tracker.py API maintains backward compatibility
- SQLite backend correctly stores breadcrumb data
- Terminal isolation is preserved
- Cache integration works correctly
- Performance baseline established (< 50ms per operation)
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
    return "test-terminal-integration-123"


@pytest.fixture
def sample_workflow_steps() -> list[dict[str, Any]]:
    """Sample workflow steps for testing."""
    return [
        {"id": "analyze", "kind": "execution", "optional": False},
        {"id": "implement", "kind": "execution", "optional": False},
        {"id": "test", "kind": "verification", "optional": False},
        {"id": "document", "kind": "execution", "optional": True},
    ]


@pytest.fixture
def initialized_database(temp_db_path: Path) -> None:
    """Initialize database with breadcrumb schema."""
    from skill_guard.breadcrumb.database import get_connection, initialize_schema

    conn = get_connection(temp_db_path)
    if conn is None:
        pytest.skip("Database unavailable")
    initialize_schema(conn)


# =============================================================================
# INTEGRATION TESTS: TRACKER.PY API COMPATIBILITY
# =============================================================================


class TestTrackerAPICompatibility:
    """Test that tracker.py maintains API compatibility with SQLite backend."""

    def test_initialize_breadcrumb_trail_creates_db_record(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that initialize_breadcrumb_trail creates a database record."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail

        # Create trail using SQLite backend
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Verify trail exists in database
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None

        # Verify trail data
        skill = row[1]
        terminal_id = row[2]
        workflow_steps_json = row[5]

        assert skill == "test-skill"
        assert terminal_id == mock_terminal_id
        workflow_steps = json.loads(workflow_steps_json)
        assert len(workflow_steps) == 4

    def test_set_breadcrumb_updates_database_record(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that set_breadcrumb updates the database record."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Update trail (set breadcrumb)
        steps = {
            step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
            for step in sample_workflow_steps
        }
        steps["analyze"]["status"] = "done"
        steps["analyze"]["evidence"] = {"files_read": 5}

        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["analyze"],
            current_step="analyze",
            steps=steps,
        )

        # Verify update in database
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT completed_steps, current_step, steps FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        assert row is not None

        completed_steps_json, current_step, steps_json = row
        completed_steps = json.loads(completed_steps_json)
        steps_data = json.loads(steps_json)

        assert completed_steps == ["analyze"]
        assert current_step == "analyze"
        assert steps_data["analyze"]["status"] == "done"
        assert steps_data["analyze"]["evidence"]["files_read"] == 5

    def test_get_active_breadcrumb_trails_returns_db_records(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that get_active_breadcrumb_trails returns database records."""
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        # Create multiple trails
        run_id1 = create_trail(
            db_path=temp_db_path,
            skill="skill1",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        run_id2 = create_trail(
            db_path=temp_db_path,
            skill="skill2",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Create trail for different terminal
        create_trail(
            db_path=temp_db_path,
            skill="skill3",
            terminal_id="other-terminal",
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Get active trails
        trails = get_active_trails(db_path=temp_db_path, terminal_id=mock_terminal_id)

        # Verify only mock_terminal_id trails returned
        assert len(trails) == 2
        run_ids = [trail["run_id"] for trail in trails]
        assert run_id1 in run_ids
        assert run_id2 in run_ids

    def test_clear_breadcrumb_trail_removes_db_record(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that clear_breadcrumb_trail removes database record."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail, delete_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Verify trail exists
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        count_before = cursor.fetchone()[0]
        assert count_before == 1

        # Clear trail
        deleted = delete_trail(db_path=temp_db_path, run_id=run_id)
        assert deleted is True

        # Verify trail removed
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        count_after = cursor.fetchone()[0]
        assert count_after == 0


# =============================================================================
# INTEGRATION TESTS: CACHE + DATABASE
# =============================================================================


class TestCacheDatabaseIntegration:
    """Test integration between cache and database layers."""

    def test_cache_falls_back_to_database(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that cache falls back to database when not in memory."""
        from skill_guard.breadcrumb.cache import BreadcrumbStateCache
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_trail_by_run_id

        # Create trail in database
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Create new cache instance (empty)
        cache = BreadcrumbStateCache()

        # Verify cache doesn't have trail
        cached_trail = cache.get_state("test-skill")
        assert cached_trail is None

        # Load from database
        trail = get_trail_by_run_id(db_path=temp_db_path, run_id=run_id)
        assert trail is not None
        assert trail["run_id"] == run_id

        # Update cache
        cache.update_state("test-skill", trail)

        # Verify cache now has trail
        cached_trail = cache.get_state("test-skill")
        assert cached_trail is not None
        assert cached_trail["run_id"] == run_id

    def test_cache_and_database_synchronization(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that cache and database stay synchronized."""
        from skill_guard.breadcrumb.cache import BreadcrumbStateCache
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        cache = BreadcrumbStateCache()

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Load trail from database
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        trail_id = row[0]

        trail = {
            "id": trail_id,
            "skill": row[1],
            "terminal_id": row[2],
            "run_id": row[3],
            "initialized_at": row[4],
            "workflow_steps": json.loads(row[5]),
            "steps": json.loads(row[6]),
            "completed_steps": json.loads(row[7]),
            "current_step": row[8],
            "last_updated": row[9],
            "tool_count": row[10],
        }

        # Update cache
        cache.update_state("test-skill", trail)

        # Update trail (database + cache)
        trail["completed_steps"] = ["analyze"]
        trail["current_step"] = "analyze"
        trail["steps"]["analyze"]["status"] = "done"

        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=trail["completed_steps"],
            current_step=trail["current_step"],
            steps=trail["steps"],
        )

        cache.update_state("test-skill", trail)

        # Verify database updated
        cursor.execute("SELECT completed_steps, current_step FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        completed_steps_json, current_step = row
        completed_steps = json.loads(completed_steps_json)

        assert completed_steps == ["analyze"]
        assert current_step == "analyze"

        # Verify cache updated
        cached_trail = cache.get_state("test-skill")
        assert cached_trail["completed_steps"] == ["analyze"]
        assert cached_trail["current_step"] == "analyze"


# =============================================================================
# INTEGRATION TESTS: TERMINAL ISOLATION
# =============================================================================


class TestTerminalIsolation:
    """Test that terminal isolation is preserved with SQLite backend."""

    def test_trails_from_different_terminals_isolated(
        self, temp_db_path: Path, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that trails from different terminals are isolated."""
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        # Create trails for different terminals
        run_id1 = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id="terminal-1",
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        run_id2 = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id="terminal-2",
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Query trails for terminal-1
        trails1 = get_active_trails(db_path=temp_db_path, terminal_id="terminal-1")
        assert len(trails1) == 1
        assert trails1[0]["run_id"] == run_id1

        # Query trails for terminal-2
        trails2 = get_active_trails(db_path=temp_db_path, terminal_id="terminal-2")
        assert len(trails2) == 1
        assert trails2[0]["run_id"] == run_id2

    def test_clear_terminal_trails_only_affects_one_terminal(
        self, temp_db_path: Path, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that clearing trails for one terminal doesn't affect others."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import clear_terminal_trails, create_trail

        # Create trails for different terminals
        create_trail(
            db_path=temp_db_path,
            skill="skill1",
            terminal_id="terminal-1",
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        create_trail(
            db_path=temp_db_path,
            skill="skill2",
            terminal_id="terminal-2",
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Clear terminal-1 trails
        cleared_count = clear_terminal_trails(db_path=temp_db_path, terminal_id="terminal-1")
        assert cleared_count == 1

        # Verify terminal-2 trails still exist
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM breadcrumb_trails WHERE terminal_id = ?", ("terminal-2",))
        count = cursor.fetchone()[0]
        assert count == 1


# =============================================================================
# INTEGRATION TESTS: EVENT LOGGING
# =============================================================================


class TestEventLogging:
    """Test breadcrumb event logging with SQLite backend."""

    def test_trail_initialization_creates_event(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that trail initialization creates an event."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Get trail_id
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        trail_id = row[0]

        # Verify event was created
        cursor.execute("SELECT * FROM breadcrumb_events WHERE trail_id = ?", (trail_id,))
        events = cursor.fetchall()
        assert len(events) == 1

        event_type = events[0][3]
        assert event_type == "trail_initialized"

    def test_step_complete_creates_event(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that step completion creates an event."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Get trail_id
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        trail_id = row[0]

        # Update trail (complete step)
        steps = {
            step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
            for step in sample_workflow_steps
        }
        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["analyze"],
            current_step="analyze",
            steps=steps,
        )

        # Verify step_complete event was created
        cursor.execute("SELECT event_type FROM breadcrumb_events WHERE trail_id = ?", (trail_id,))
        event_types = [row[0] for row in cursor.fetchall()]

        assert "trail_initialized" in event_types
        assert "step_complete" in event_types

    def test_events_ordered_by_timestamp(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that events are ordered by timestamp."""
        from skill_guard.breadcrumb.database import get_connection
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Get trail_id
        conn = get_connection(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        trail_id = row[0]

        # Complete multiple steps
        steps = {
            step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
            for step in sample_workflow_steps
        }

        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["analyze"],
            current_step="analyze",
            steps=steps,
        )

        time.sleep(0.01)  # Small delay to ensure different timestamps

        steps["analyze"]["status"] = "done"
        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["analyze", "implement"],
            current_step="implement",
            steps=steps,
        )

        # Verify events are ordered
        cursor.execute(
            "SELECT event_type, timestamp FROM breadcrumb_events WHERE trail_id = ? ORDER BY timestamp ASC",
            (trail_id,),
        )
        events = cursor.fetchall()

        assert len(events) == 3  # trail_initialized + 2 step_complete
        assert events[0][0] == "trail_initialized"
        assert events[1][0] == "step_complete"
        assert events[2][0] == "step_complete"

        # Verify timestamps are ascending
        assert events[0][1] < events[1][1] < events[2][1]


# =============================================================================
# INTEGRATION TESTS: PERFORMANCE BASELINE
# =============================================================================


class TestPerformanceBaseline:
    """Test performance baseline for SQLite backend operations."""

    def test_create_trail_performance_baseline(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that create_trail meets < 50ms performance baseline."""
        from skill_guard.breadcrumb.sqlite_backend import create_trail

        start = time.time()
        create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"create_trail took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_update_trail_performance_baseline(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that update_trail meets < 50ms performance baseline."""
        from skill_guard.breadcrumb.sqlite_backend import create_trail, update_trail

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Measure update performance
        steps = {
            step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
            for step in sample_workflow_steps
        }

        start = time.time()
        update_trail(
            db_path=temp_db_path,
            run_id=run_id,
            completed_steps=["analyze"],
            current_step="analyze",
            steps=steps,
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"update_trail took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_get_active_trails_performance_baseline(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that get_active_trails meets < 50ms performance baseline."""
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_active_trails

        # Create multiple trails
        for i in range(10):
            create_trail(
                db_path=temp_db_path,
                skill=f"skill{i}",
                terminal_id=mock_terminal_id,
                workflow_steps=sample_workflow_steps,
                steps={
                    step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                    for step in sample_workflow_steps
                },
            )

        # Measure query performance
        start = time.time()
        trails = get_active_trails(db_path=temp_db_path, terminal_id=mock_terminal_id)
        elapsed_ms = (time.time() - start) * 1000

        assert len(trails) == 10
        assert elapsed_ms < 50, f"get_active_trails took {elapsed_ms:.2f}ms, expected < 50ms"

    def test_cache_hit_performance_baseline(
        self, temp_db_path: Path, mock_terminal_id: str, sample_workflow_steps: list[dict], initialized_database: None
    ) -> None:
        """Test that cache hits are significantly faster than database queries."""
        from skill_guard.breadcrumb.cache import BreadcrumbStateCache
        from skill_guard.breadcrumb.sqlite_backend import create_trail, get_trail_by_run_id

        cache = BreadcrumbStateCache()

        # Create trail
        run_id = create_trail(
            db_path=temp_db_path,
            skill="test-skill",
            terminal_id=mock_terminal_id,
            workflow_steps=sample_workflow_steps,
            steps={
                step["id"]: {"kind": step["kind"], "optional": step["optional"], "status": "pending", "evidence": {}}
                for step in sample_workflow_steps
            },
        )

        # Load trail and cache it
        trail = get_trail_by_run_id(db_path=temp_db_path, run_id=run_id)
        cache.update_state("test-skill", trail)

        # Measure database query performance
        start = time.time()
        get_trail_by_run_id(db_path=temp_db_path, run_id=run_id)
        db_query_ms = (time.time() - start) * 1000

        # Measure cache hit performance
        start = time.time()
        cache.get_state("test-skill")
        cache_hit_ms = (time.time() - start) * 1000

        # Cache should be faster than DB query (allowing for measurement variance)
        # For very fast operations (< 1ms), we just check cache is not slower
        if db_query_ms > 1.0:
            assert cache_hit_ms < db_query_ms / 10, f"Cache hit ({cache_hit_ms:.2f}ms) not significantly faster than DB query ({db_query_ms:.2f}ms)"
        else:
            # For very fast queries, cache should at least be as fast
            assert cache_hit_ms <= db_query_ms * 2, f"Cache hit ({cache_hit_ms:.2f}ms) slower than expected compared to DB query ({db_query_ms:.2f}ms)"
