"""
Characterization tests for BUG-016: non-atomic delete-then-rename in _atomic_write_json.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
The bug: _atomic_write_json uses unlink() then rename() as separate operations,
creating a data-loss window between them if the process crashes or rename fails.

Run with: pytest P:/packages/skill-guard/tests/test_atomic_write_gap.py -v
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from skill_guard.execution_store import ExecutionStore


class TestAtomicWriteGap:
    """Tests showing the non-atomic delete-then-rename pattern."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create ExecutionStore with temporary console dir."""
        with patch.object(ExecutionStore, 'console_dir', return_value=tmp_path):
            yield ExecutionStore()

    def test_unlink_then_rename_sequence(self, store, tmp_path):
        """
        Characterization: _atomic_write_json calls unlink BEFORE rename.

        Current sequence:
        1. path.unlink()  <- deletes existing file
        2. tmp.rename(path)  <- renames temp to target

        If crash occurs between step 1 and 2, data is lost.
        """
        state_file = tmp_path / "execution-state.json"
        data = {"test": "value"}

        # Create existing file to trigger the unlink path
        state_file.write_text("{}", encoding="utf-8")

        calls = []

        original_unlink = Path.unlink
        original_rename = Path.rename

        def tracked_unlink(self):
            calls.append(('unlink', str(self)))
            return original_unlink(self)

        def tracked_rename(self, target):
            calls.append(('rename', str(self), str(target)))
            return original_rename(self, target)

        with patch.object(Path, 'unlink', tracked_unlink):
            with patch.object(Path, 'rename', tracked_rename):
                store._atomic_write_json(state_file, data)

        # Verify unlink happens BEFORE rename
        assert len(calls) == 2, f"Expected 2 calls, got {len(calls)}: {calls}"
        assert calls[0][0] == 'unlink', f"First call should be unlink, got: {calls[0]}"
        assert calls[1][0] == 'rename', f"Second call should be rename, got: {calls[1]}"
        assert calls[0][1] == str(state_file), f"Unlink should target original path: {calls[0][1]}"

    def test_no_rollback_on_rename_failure_after_unlink(self, store, tmp_path):
        """
        Characterization: If rename fails after unlink, data is permanently lost.

        Current behavior: No rollback mechanism exists. If rename() raises after
        unlink() succeeds, the original data is gone with no recovery path.
        """
        state_file = tmp_path / "execution-state.json"
        original_data = {"original": "data"}
        new_data = {"new": "data"}

        # Create existing file
        state_file.write_text(json.dumps(original_data), encoding="utf-8")

        rename_called = []

        def failing_rename(self, target):
            rename_called.append((str(self), str(target)))
            raise OSError("Simulated rename failure")

        with patch.object(Path, 'rename', failing_rename):
            with pytest.raises(OSError):
                store._atomic_write_json(state_file, new_data)

        # Verify unlink was called (data deleted)
        assert state_file.exists() is False, "File should be deleted after unlink"

        # Verify no rollback occurred - data is simply gone
        assert rename_called[0][0] == str(state_file.with_suffix(".json.tmp"))

    def test_data_loss_window_between_unlink_and_rename(self, store, tmp_path):
        """
        Characterization: There is a window between unlink and rename where
        no file exists at the target path.

        This window could cause:
        - Other processes to see missing file
        - Race conditions in multi-threaded access
        - Data loss if process crashes
        """
        state_file = tmp_path / "execution-state.json"
        state_file.write_text("{}", encoding="utf-8")

        file_exists_during_calls = []

        original_unlink = Path.unlink
        original_rename = Path.rename

        def check_exists_unlink(self):
            file_exists_during_calls.append(('before_unlink', str(self), Path(self).exists()))
            result = original_unlink(self)
            file_exists_during_calls.append(('after_unlink', str(self), Path(self).exists()))
            return result

        def check_exists_rename(self, target):
            file_exists_during_calls.append(('before_rename', str(self), Path(self).exists()))
            result = original_rename(self, target)
            file_exists_during_calls.append(('after_rename', str(target), Path(target).exists()))
            return result

        with patch.object(Path, 'unlink', check_exists_unlink):
            with patch.object(Path, 'rename', check_exists_rename):
                store._atomic_write_json(state_file, {"test": "value"})

        # Find the gap: after unlink but before rename completes
        gap_indices = [
            i for i, (stage, path, exists) in enumerate(file_exists_during_calls)
            if 'after_unlink' in stage and not exists
        ]

        # There should be at least one check after unlink where file doesn't exist
        after_unlink_checks = [(s, p, e) for s, p, e in file_exists_during_calls if 'unlink' in s]
        has_gap = any(not e for _, _, e in after_unlink_checks if 'after' in _)

        assert has_gap, f"No data-loss gap detected. File exists at all checks: {file_exists_during_calls}"


class TestAtomicWritePatternAnalysis:
    """Analysis of the correct vs incorrect atomic write patterns."""

    def test_correct_atomic_write_should_use_rename_overwrite(self):
        """
        Correct atomic write pattern:
        1. Write to temp file
        2. Rename temp to target (overwrites atomically on POSIX, or fails)

        The rename operation is atomic on the same filesystem:
        - On POSIX: rename() is atomic - target either exists fully or not at all
        - On Windows: rename() fails if target exists (different behavior!)

        The problem with current code: unlink before rename is WRONG because:
        - Creates a window where file doesn't exist
        - If rename fails, data is gone forever
        - On Windows, rename to existing path fails, so unlink was added "to fix" that
          but this creates the data-loss window
        """
        # This test documents the CORRECT pattern that SHOULD be used
        # The correct approach on Windows is to use replace() which IS atomic
        # and handles the overwriting case

        # Document that the current unlink+rename pattern is fundamentally broken
        # as a "fix" for Windows rename behavior
        pass