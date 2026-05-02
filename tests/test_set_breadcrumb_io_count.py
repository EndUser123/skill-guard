"""Characterization tests for set_breadcrumb() I/O behavior.

These tests CAPTURE CURRENT BEHAVIOR before optimization.
Run with: pytest tests/test_set_breadcrumb_io_count.py -v

PERF-003: set_breadcrumb() makes 4 separate I/O calls per update:
  1. SQLite update (sqlite_backend.update_trail) - CONDITIONAL on _db_initialized
  2. JSONL log append (AppendOnlyBreadcrumbLog.append) - ALWAYS fires
  3. Cache update (_cache.update_state) - ALWAYS fires
  4. JSON file rewrite with fsync (open + write + flush + fsync) - ALWAYS fires

This test verifies these I/O operations occur and are NOT batched/deferred.
"""

import os
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def clean_tracker_state():
    """Clean tracker state before and after each test."""
    from skill_guard.breadcrumb import tracker

    # Clean before test
    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()

    # Ensure _db_initialized is False so SQLite update doesn't mask our counts
    original_db_init = tracker._db_initialized
    tracker._db_initialized = False

    yield

    # Clean after test
    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()
    tracker._db_initialized = original_db_init


@pytest.fixture
def mock_workflow_steps():
    """Provide mock workflow steps."""
    mock_result = MagicMock()
    mock_result.steps = [
        {"id": "step1", "kind": "execution", "optional": False},
        {"id": "step2", "kind": "execution", "optional": False},
    ]
    mock_result.parse_error = None
    return mock_result


class TestSetBreadcrumbIOCount:
    """Tests for set_breadcrumb() I/O operation count."""

    def test_set_breadcrumb_makes_multiple_io_operations(
        self, clean_tracker_state, mock_workflow_steps
    ):
        """Characterization: set_breadcrumb() makes multiple I/O calls per invocation.

        Given: A valid breadcrumb trail is initialized
        When: set_breadcrumb("test_skill", "step1") is called
        Then: JSONL log + cache update + JSON file write with fsync fire
        """
        from skill_guard.breadcrumb import tracker

        # Patch workflow steps loading
        with patch.object(tracker, "_load_workflow_steps", return_value=mock_workflow_steps):
            # Initialize trail
            tracker.initialize_breadcrumb_trail(skill_name="test_skill")

            # Verify trail exists
            trail = tracker._cache.get_state("test_skill")
            assert trail is not None, "Trail should exist after init"

            # Track I/O calls
            log_append_calls = 0
            cache_update_calls = 0
            file_open_count = 0
            fsync_count = 0

            mock_log_instance = MagicMock()

            def track_log_append(entry):
                nonlocal log_append_calls
                log_append_calls += 1
                return mock_log_instance.append(entry)

            original_cache_update = tracker._cache.update_state

            def track_cache_update(skill, state):
                nonlocal cache_update_calls
                cache_update_calls += 1
                return original_cache_update(skill, state)

            # Create mock file that will be returned by our mocked open
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.write = MagicMock()
            mock_file.flush = MagicMock()
            mock_file.fileno = MagicMock(return_value=3)

            def track_open(path, mode='r', *args, **kwargs):
                nonlocal file_open_count
                if 'w' in mode:
                    file_open_count += 1
                return mock_file

            def track_fsync(fd):
                nonlocal fsync_count
                fsync_count += 1
                return 0

            # Apply tracking patches
            tracker.AppendOnlyBreadcrumbLog = lambda skill: MagicMock(append=track_log_append)
            tracker._cache.update_state = track_cache_update

            try:
                with patch("builtins.open", track_open):
                    with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                        tracker.set_breadcrumb("test_skill", "step1")

                # Report results
                total_io = log_append_calls + cache_update_calls + file_open_count + fsync_count
                print(f"\nI/O counts: log={log_append_calls}, cache={cache_update_calls}, open={file_open_count}, fsync={fsync_count}")

                assert total_io >= 3, f"Expected >= 3 I/O operations, got {total_io}"
                assert log_append_calls >= 1, "Log append should be called"
                assert cache_update_calls >= 1, "Cache update should be called"
                assert file_open_count >= 1, "File open should be called"
                assert fsync_count >= 1, "fsync should be called"
            finally:
                # Restore
                tracker._cache.update_state = original_cache_update

    def test_jsonl_log_append_is_called(self, clean_tracker_state, mock_workflow_steps):
        """Characterization: JSONL log append is called on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        mock_instance = MagicMock()
        original_log = tracker.AppendOnlyBreadcrumbLog
        tracker.AppendOnlyBreadcrumbLog = lambda skill: mock_instance

        try:
            with patch.object(tracker, "_load_workflow_steps", return_value=mock_workflow_steps):
                tracker.initialize_breadcrumb_trail(skill_name="test_skill")
                mock_instance.reset_mock()

                tracker.set_breadcrumb("test_skill", "step1")

                assert mock_instance.append.call_count >= 1, (
                    "AppendOnlyBreadcrumbLog.append should be called on every set_breadcrumb"
                )
        finally:
            tracker.AppendOnlyBreadcrumbLog = original_log

    def test_cache_update_is_called(self, clean_tracker_state, mock_workflow_steps):
        """Characterization: cache update is called on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        update_called = False
        original_cache_update = tracker._cache.update_state

        def mock_update(skill, state):
            nonlocal update_called
            update_called = True
            return original_cache_update(skill, state)

        tracker._cache.update_state = mock_update

        try:
            with patch.object(tracker, "_load_workflow_steps", return_value=mock_workflow_steps):
                tracker.initialize_breadcrumb_trail(skill_name="test_skill")
                update_called = False

                tracker.set_breadcrumb("test_skill", "step1")

                assert update_called, "_cache.update_state should be called on every set_breadcrumb"
        finally:
            tracker._cache.update_state = original_cache_update

    def test_json_file_write_with_fsync_is_called(self, clean_tracker_state, mock_workflow_steps):
        """Characterization: JSON file is rewritten with fsync on every set_breadcrumb."""
        from skill_guard.breadcrumb import tracker

        file_open_count = 0
        fsync_count = 0

        # Create mock file
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.write = MagicMock()
        mock_file.flush = MagicMock()
        mock_file.fileno = MagicMock(return_value=3)

        def track_open(path, mode='r', *args, **kwargs):
            nonlocal file_open_count
            if 'w' in mode:
                file_open_count += 1
            return mock_file

        def track_fsync(fd):
            nonlocal fsync_count
            fsync_count += 1
            return 0

        with patch.object(tracker, "_load_workflow_steps", return_value=mock_workflow_steps):
            tracker.initialize_breadcrumb_trail(skill_name="test_skill")

            file_open_count = 0
            fsync_count = 0

            with patch("builtins.open", track_open):
                with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                    tracker.set_breadcrumb("test_skill", "step1")

            assert file_open_count >= 1, "JSON file should be opened for writing"
            assert fsync_count >= 1, "os.fsync should be called"

    def test_io_operations_are_not_batched(self, clean_tracker_state, mock_workflow_steps):
        """Characterization: I/O operations execute immediately, not batched."""
        from skill_guard.breadcrumb import tracker

        file_open_count = 0
        fsync_count = 0

        # Create mock file
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.write = MagicMock()
        mock_file.flush = MagicMock()
        mock_file.fileno = MagicMock(return_value=3)

        def track_open(path, mode='r', *args, **kwargs):
            nonlocal file_open_count
            if 'w' in mode:
                file_open_count += 1
            return mock_file

        def track_fsync(fd):
            nonlocal fsync_count
            fsync_count += 1
            return 0

        mock_log_instance = MagicMock()
        original_log = tracker.AppendOnlyBreadcrumbLog
        tracker.AppendOnlyBreadcrumbLog = lambda skill: mock_log_instance

        try:
            with patch.object(tracker, "_load_workflow_steps", return_value=mock_workflow_steps):
                tracker.initialize_breadcrumb_trail(skill_name="test_skill")

                file_open_count = 0
                fsync_count = 0
                mock_log_instance.reset_mock()

                with patch("builtins.open", track_open):
                    with patch("skill_guard.breadcrumb.tracker.os.fsync", track_fsync):
                        tracker.set_breadcrumb("test_skill", "step1")

                assert file_open_count == 1, f"Single open call expected, got {file_open_count}"
                assert fsync_count == 1, f"Single fsync call expected, got {fsync_count}"
                assert mock_log_instance.append.call_count == 1, f"Single log append expected, got {mock_log_instance.append.call_count}"
        finally:
            tracker.AppendOnlyBreadcrumbLog = original_log


if __name__ == "__main__":
    pytest.main([__file__, "-v"])