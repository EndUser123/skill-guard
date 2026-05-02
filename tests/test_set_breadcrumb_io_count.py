"""Characterization tests for set_breadcrumb() I/O behavior.

These tests CAPTURE CURRENT BEHAVIOR before optimization.
Run with: pytest tests/test_set_breadcrumb_io_count.py -v

PERF-003: set_breadcrumb() makes 4 separate I/O calls per update:
  1. SQLite update (sqlite_backend.update_trail)
  2. JSONL log append (AppendOnlyBreadcrumbLog.append)
  3. Cache update (_cache.update_state)
  4. JSON file rewrite with fsync (open + write + flush + fsync)

This test verifies these 4 I/O operations occur and are NOT batched/deferred.
"""

import os
import builtins
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSetBreadcrumbIOCount:
    """Tests for set_breadcrumb() I/O operation count."""

    def test_set_breadcrumb_makes_four_io_operations(self):
        """Characterization: set_breadcrumb() makes 4+ I/O calls per invocation.

        Given: A valid breadcrumb trail is initialized
        When: set_breadcrumb("test_skill", "step1") is called
        Then: SQLite update + JSONL log + cache update + JSON file write with fsync
        """
        from skill_guard.breadcrumb import tracker

        # Create mock workflow steps that return valid steps
        dummy_steps = [
            {"id": "step1", "kind": "execution", "optional": False},
            {"id": "step2", "kind": "execution", "optional": False},
        ]
        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = dummy_steps
        mock_workflow_result.parse_error = None

        # Track all I/O calls
        io_calls = {
            "sqlite_update": 0,
            "log_append": 0,
            "cache_update": 0,
            "file_open": 0,
            "fsync": 0,
        }

        original_load = tracker._load_workflow_steps
        original_update_trail = tracker.sqlite_backend.update_trail
        original_log_class = tracker.AppendOnlyBreadcrumbLog
        original_cache_update = tracker._cache.update_state

        def mock_load_steps(skill_name):
            return mock_workflow_result

        def mock_update_trail(*args, **kwargs):
            io_calls["sqlite_update"] += 1
            return original_update_trail(*args, **kwargs)

        mock_log_instance = MagicMock()
        def mock_log_append(entry):
            io_calls["log_append"] += 1
            return mock_log_instance.append(entry)

        def mock_cache_update(skill, state):
            io_calls["cache_update"] += 1
            return original_cache_update(skill, state)

        # Track file operations
        file_open_count = 0
        fsync_count = 0
        original_open = builtins.open

        def track_open(path, mode='r', *args, **kwargs):
            nonlocal file_open_count
            if 'w' in mode:
                file_open_count += 1
            return original_open(path, mode, *args, **kwargs)

        def track_fsync(fd):
            nonlocal fsync_count
            fsync_count += 1
            return os.fsync(fd)

        # Apply patches at module level
        tracker._load_workflow_steps = mock_load_steps
        tracker.sqlite_backend.update_trail = mock_update_trail
        tracker.AppendOnlyBreadcrumbLog = lambda skill: MagicMock(append=mock_log_append)
        tracker._cache.update_state = mock_cache_update

        try:
            # Clear cache and init trail
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()
            tracker.initialize_breadcrumb_trail(skill_name="test_skill")

            # Get trail and check step is valid
            trail = tracker._cache.get_state("test_skill")
            assert trail is not None, "Trail should exist after init"
            assert "step1" in trail.get("steps", {}), "step1 should be in steps"

            # Reset call counts after init
            io_calls = {k: 0 for k in io_calls}
            file_open_count = 0
            fsync_count = 0

            # Patch file operations for set_breadcrumb only
            with patch("builtins.open", track_open):
                with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                    # Act - call set_breadcrumb
                    tracker.set_breadcrumb("test_skill", "step1")

            io_calls["file_open"] = file_open_count
            io_calls["fsync"] = fsync_count

            # Report results
            total_io = sum(io_calls.values())
            print(f"\nI/O call counts: {io_calls}")
            print(f"Total I/O operations: {total_io}")

            assert total_io >= 4, (
                f"Expected >= 4 I/O operations, got: {io_calls}"
            )
        finally:
            # Restore originals
            tracker._load_workflow_steps = original_load
            tracker.sqlite_backend.update_trail = original_update_trail
            tracker.AppendOnlyBreadcrumbLog = original_log_class
            tracker._cache.update_state = original_cache_update

    def test_sqlite_update_is_called(self):
        """Characterization: SQLite backend update is called when run_id exists."""
        from skill_guard.breadcrumb import tracker

        # Create mock workflow steps
        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = [{"id": "step1", "kind": "execution", "optional": False}]
        mock_workflow_result.parse_error = None

        update_called = False
        original_update = tracker.sqlite_backend.update_trail

        def mock_update(*args, **kwargs):
            nonlocal update_called
            update_called = True
            return original_update(*args, **kwargs)

        tracker.sqlite_backend.update_trail = mock_update

        try:
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()
            tracker._load_workflow_steps = lambda s: mock_workflow_result

            tracker.initialize_breadcrumb_trail(skill_name="test_skill")
            tracker.set_breadcrumb("test_skill", "step1")

            assert update_called, "SQLite update should be called when run_id is set in trail"
        finally:
            tracker.sqlite_backend.update_trail = original_update

    def test_jsonl_log_append_is_called(self):
        """Characterization: JSONL log append is called on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = [{"id": "step1", "kind": "execution", "optional": False}]
        mock_workflow_result.parse_error = None

        mock_instance = MagicMock()
        original_log = tracker.AppendOnlyBreadcrumbLog
        tracker.AppendOnlyBreadcrumbLog = lambda s: mock_instance

        try:
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()
            tracker._load_workflow_steps = lambda s: mock_workflow_result

            tracker.initialize_breadcrumb_trail(skill_name="test_skill")
            mock_instance.reset_mock()

            tracker.set_breadcrumb("test_skill", "step1")

            assert mock_instance.append.call_count >= 1, (
                "AppendOnlyBreadcrumbLog.append should be called on every set_breadcrumb"
            )
        finally:
            tracker.AppendOnlyBreadcrumbLog = original_log

    def test_cache_update_is_called(self):
        """Characterization: cache update is called on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = [{"id": "step1", "kind": "execution", "optional": False}]
        mock_workflow_result.parse_error = None

        update_called = False
        original_cache_update = tracker._cache.update_state

        def mock_update(skill, state):
            nonlocal update_called
            update_called = True
            return original_cache_update(skill, state)

        tracker._cache.update_state = mock_update

        try:
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()
            tracker._load_workflow_steps = lambda s: mock_workflow_result

            tracker.initialize_breadcrumb_trail(skill_name="test_skill")
            update_called = False

            tracker.set_breadcrumb("test_skill", "step1")

            assert update_called, "_cache.update_state should be called on every set_breadcrumb"
        finally:
            tracker._cache.update_state = original_cache_update

    def test_json_file_write_with_fsync_is_called(self):
        """Characterization: JSON file is rewritten with fsync on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = [{"id": "step1", "kind": "execution", "optional": False}]
        mock_workflow_result.parse_error = None

        file_open_count = 0
        fsync_count = 0
        original_open = builtins.open

        def track_open(path, mode='r', *args, **kwargs):
            nonlocal file_open_count
            if 'w' in mode:
                file_open_count += 1
            return original_open(path, mode, *args, **kwargs)

        def track_fsync(fd):
            nonlocal fsync_count
            fsync_count += 1
            return os.fsync(fd)

        tracker._load_workflow_steps = lambda s: mock_workflow_result

        try:
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()

            tracker.initialize_breadcrumb_trail(skill_name="test_skill")

            file_open_count = 0
            fsync_count = 0

            with patch("builtins.open", track_open):
                with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                    tracker.set_breadcrumb("test_skill", "step1")

            assert file_open_count >= 1, "JSON file should be opened for writing on every set_breadcrumb"
            assert fsync_count >= 1, "os.fsync should be called on every set_breadcrumb"
        finally:
            tracker._load_workflow_steps = lambda s: original_load if 'original_load' in dir() else mock_workflow_result

    def test_io_operations_are_not_batched(self):
        """Characterization: I/O operations execute immediately, not batched.

        If operations were batched/deferred, mocking open would prevent
        subsequent file I/O from occurring during set_breadcrumb call.
        """
        from skill_guard.breadcrumb import tracker

        mock_workflow_result = MagicMock()
        mock_workflow_result.steps = [{"id": "step1", "kind": "execution", "optional": False}]
        mock_workflow_result.parse_error = None

        file_open_count = 0
        fsync_count = 0
        original_open = builtins.open

        def track_open(path, mode='r', *args, **kwargs):
            nonlocal file_open_count
            if 'w' in mode:
                file_open_count += 1
            return original_open(path, mode, *args, **kwargs)

        def track_fsync(fd):
            nonlocal fsync_count
            fsync_count += 1
            return os.fsync(fd)

        mock_log_instance = MagicMock()
        original_log = tracker.AppendOnlyBreadcrumbLog
        tracker.AppendOnlyBreadcrumbLog = lambda s: mock_log_instance

        try:
            tracker._cache._cache.clear()
            tracker._cache._access_times.clear()
            tracker._load_workflow_steps = lambda s: mock_workflow_result

            tracker.initialize_breadcrumb_trail(skill_name="test_skill")

            file_open_count = 0
            fsync_count = 0
            mock_log_instance.reset_mock()

            with patch("builtins.open", track_open):
                with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                    tracker.set_breadcrumb("test_skill", "step1")

            # All 3 file-related operations should occur in single call
            assert file_open_count == 1, f"Single open call expected (not batched), got {file_open_count}"
            assert fsync_count == 1, f"Single fsync call expected (not batched), got {fsync_count}"
            assert mock_log_instance.append.call_count == 1, f"Single log append expected (not batched), got {mock_log_instance.append.call_count}"
        finally:
            tracker.AppendOnlyBreadcrumbLog = original_log


if __name__ == "__main__":
    pytest.main([__file__, "-v"])