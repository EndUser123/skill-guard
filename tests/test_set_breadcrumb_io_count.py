"""Characterization tests for set_breadcrumb() I/O behavior.

These tests CAPTURE CURRENT BEHAVIOR before optimization.
Run with: pytest tests/test_set_breadcrumb_io_count.py -v

PERF-003: set_breadcrumb() makes 4 separate I/O calls per update:
  1. SQLite update (sqlite_backend.update_trail)
  2. JSONL log append (AppendOnlyBreadcrumbLog.append)
  3. Cache update (_cache.update_state) — in-memory, but tracked
  4. JSON file rewrite with fsync (open + write + flush + fsync)

This test verifies these 4 I/O operations occur and are NOT batched/deferred.
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest


class TestSetBreadcrumbIOCount:
    """Tests for set_breadcrumb() I/O operation count."""

    @pytest.fixture
    def mock_sqlite_backend(self):
        """Patch sqlite_backend.update_trail to count calls."""
        with patch(
            "skill_guard.breadcrumb.tracker.sqlite_backend"
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_append_log(self):
        """Patch AppendOnlyBreadcrumbLog.append to count calls."""
        with patch(
            "skill_guard.breadcrumb.tracker.AppendOnlyBreadcrumbLog"
        ) as mock_class:
            # Return a mock instance with append method
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_cache_update(self):
        """Patch _cache.update_state to count calls."""
        with patch(
            "skill_guard.breadcrumb.tracker._cache"
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_open(self):
        """Patch builtin open to count file write operations."""
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.flush = MagicMock()
        mock_file.fileno = MagicMock(return_value=3)

        with patch("builtins.open", return_value=mock_file) as mock:
            yield mock

    @pytest.fixture
    def mock_os_fsync(self):
        """Patch os.fsync to count calls."""
        with patch("skill_guard.breadcrumb.tracker.os.fsync") as mock:
            yield mock

    @pytest.fixture
    def initialized_trail(self, mock_sqlite_backend, mock_append_log, mock_cache_update):
        """Initialize a breadcrumb trail so set_breadcrumb has valid state."""
        from skill_guard.breadcrumb.tracker import initialize_breadcrumb_trail

        # Call init which sets up the trail
        initialize_breadcrumb_trail(
            skill_name="test_skill",
            workflow_steps=["step1", "step2"],
            steps={"step1": {}, "step2": {}},
        )
        # Reset mock call counts after init
        mock_append_log.reset_mock()

    def test_set_breadcrumb_makes_four_io_operations(
        self,
        mock_sqlite_backend,
        mock_append_log,
        mock_cache_update,
        mock_open,
        mock_os_fsync,
        initialized_trail,
    ):
        """Characterization: set_breadcrumb() makes 4+ I/O calls per invocation.

        Given: A valid breadcrumb trail is initialized
        When: set_breadcrumb("test_skill", "step1") is called
        Then: SQLite update + JSONL log + cache update + JSON file write with fsync
        """
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        # Reset call counts
        mock_sqlite_backend.update_trail.reset_mock()
        mock_append_log.reset_mock()
        mock_cache_update.update_state.reset_mock()
        mock_open.reset_mock()
        mock_os_fsync.reset_mock()

        # Act
        set_breadcrumb("test_skill", "step1")

        # Assert: SQLite update (if run_id exists)
        sqlite_calls = mock_sqlite_backend.update_trail.call_count

        # Assert: JSONL log append
        log_append_calls = mock_append_log.append.call_count

        # Assert: Cache update
        cache_update_calls = mock_cache_update.update_state.call_count

        # Assert: JSON file write (open called once for "w" mode)
        file_open_calls = mock_open.call_count

        # Assert: fsync called once
        fsync_calls = mock_os_fsync.call_count

        total_io = sqlite_calls + log_append_calls + cache_update_calls + file_open_calls + fsync_calls

        assert total_io >= 4, (
            f"Expected >= 4 I/O operations, got: "
            f"SQLite={sqlite_calls}, JSONL_append={log_append_calls}, "
            f"cache_update={cache_update_calls}, file_open={file_open_calls}, fsync={fsync_calls}"
        )

    def test_sqlite_update_is_called(
        self, mock_sqlite_backend, initialized_trail
    ):
        """Characterization: SQLite backend update is called when run_id exists."""
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        mock_sqlite_backend.update_trail.reset_mock()
        set_breadcrumb("test_skill", "step1")

        assert mock_sqlite_backend.update_trail.call_count >= 1, (
            "SQLite update should be called when run_id is set in trail"
        )

    def test_jsonl_log_append_is_called(
        self, mock_append_log, initialized_trail
    ):
        """Characterization: JSONL log append is called on every set_breadcrumb."""
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        mock_append_log.reset_mock()
        set_breadcrumb("test_skill", "step1")

        assert mock_append_log.append.call_count >= 1, (
            "AppendOnlyBreadcrumbLog.append should be called on every set_breadcrumb"
        )

    def test_cache_update_is_called(
        self, mock_cache_update, initialized_trail
    ):
        """Characterization: cache update is called on every set_breadcrumb."""
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        mock_cache_update.reset_mock()
        set_breadcrumb("test_skill", "step1")

        assert mock_cache_update.update_state.call_count >= 1, (
            "_cache.update_state should be called on every set_breadcrumb"
        )

    def test_json_file_write_with_fsync_is_called(
        self, mock_open, mock_os_fsync, initialized_trail
    ):
        """Characterization: JSON file is rewritten with fsync on every set_breadcrumb."""
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        mock_open.reset_mock()
        mock_os_fsync.reset_mock()
        set_breadcrumb("test_skill", "step1")

        assert mock_open.call_count >= 1, (
            "JSON file should be opened for writing on every set_breadcrumb"
        )
        assert mock_os_fsync.call_count >= 1, (
            "os.fsync should be called on every set_breadcrumb"
        )

    def test_io_operations_are_not_batched(self, mock_open, mock_os_fsync, mock_append_log, initialized_trail):
        """Characterization: I/O operations execute immediately, not batched.

        If operations were batched/deferred, mocking open would prevent
        subsequent file I/O from occurring during set_breadcrumb call.
        """
        from skill_guard.breadcrumb.tracker import set_breadcrumb

        mock_open.reset_mock()
        mock_os_fsync.reset_mock()
        mock_append_log.reset_mock()

        set_breadcrumb("test_skill", "step1")

        # All 3 file-related operations should occur in single call
        assert mock_open.call_count == 1, "Single open call expected (not batched)"
        assert mock_os_fsync.call_count == 1, "Single fsync call expected (not batched)"
        assert mock_append_log.append.call_count == 1, "Single log append expected (not batched)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])