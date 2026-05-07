r"""
RED phase tests for BUG-016: non-atomic delete-then-rename in _atomic_write_json.

These tests assert CORRECT behavior and FAIL against the buggy implementation.
The bug: _atomic_write_json uses unlink() then rename() as separate operations,
creating a data-loss window. Correct behavior: use os.replace() for atomic overwrite.

Run with: pytest P:\\\\packages/skill-guard/tests/test_atomic_write_gap.py -v
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch

from skill_guard.execution_store import ArtifactsExecutionStore


class TestAtomicWriteCorrectBehavior:
    """Tests asserting the CORRECT atomic write behavior."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create ArtifactsExecutionStore with temp artifacts root."""
        with patch.object(ArtifactsExecutionStore, 'ARTIFACTS_ROOT', tmp_path):
            yield ArtifactsExecutionStore("test_console")

    def test_no_unlink_before_rename(self, store, tmp_path):
        """
        CORRECT behavior: unlink should NOT be called before rename.

        The atomic write should use os.replace() which atomically overwrites
        the target file. No separate unlink call should occur.
        """
        state_file = tmp_path / "execution-state.json"
        state_file.write_text("{}", encoding="utf-8")

        calls = []

        def tracked_unlink(self):
            calls.append(('unlink', str(self)))
            raise AssertionError("unlink should NOT be called - use os.replace() instead")

        def tracked_rename(self, target):
            calls.append(('rename', str(self), str(target)))
            return Path.rename(self, target)

        with patch.object(Path, 'unlink', tracked_unlink):
            with patch.object(Path, 'rename', tracked_rename):
                store._atomic_write_json(state_file, {"test": "value"})

        # With os.replace(), unlink should not be called at all
        unlink_calls = [c for c in calls if c[0] == 'unlink']
        assert len(unlink_calls) == 0, f"unlink was called {len(unlink_calls)} times - should use os.replace() for atomic overwrite"

    def test_uses_os_replace_for_atomic_overwrite(self, store, tmp_path):
        """
        CORRECT behavior: use os.replace() for atomic overwrite.

        os.replace() atomically replaces the target file - no gap, no data loss.
        This is the correct approach on both POSIX and Windows.
        """
        state_file = tmp_path / "execution-state.json"
        state_file.write_text("{}", encoding="utf-8")

        replace_called = []

        original_replace = os.replace

        def tracked_replace(src, dst):
            replace_called.append((src, dst))
            return original_replace(src, dst)

        with patch('os.replace', tracked_replace):
            store._atomic_write_json(state_file, {"test": "value"})

        assert len(replace_called) == 1, f"os.replace() should be called once, got {len(replace_called)} calls"
        src, dst = replace_called[0]
        assert src.endswith('.tmp'), f"Source should be temp file, got: {src}"
        assert str(state_file) == dst, f"Destination should be state_file, got: {dst}"

    def test_no_data_loss_gap_during_write(self, store, tmp_path):
        """
        CORRECT behavior: file should never disappear during atomic write.

        With os.replace(), the target file exists atomically - either the old
        content or new content, never missing.
        """
        state_file = tmp_path / "execution-state.json"
        original_content = {"original": "data"}
        state_file.write_text(json.dumps(original_content), encoding="utf-8")

        file_existed_during_write = []

        # Patch os.replace to check file existence
        original_replace = os.replace

        def tracked_replace(src, dst):
            # Before replace, the state file should still exist with old content
            file_existed_during_write.append(('before', state_file.exists()))
            # After replace, the state file should exist with new content
            result = original_replace(src, dst)
            file_existed_during_write.append(('after', state_file.exists()))
            return result

        with patch('os.replace', tracked_replace):
            store._atomic_write_json(state_file, {"new": "data"})

        # File should exist at ALL times during the write operation
        assert all(exists for _, exists in file_existed_during_write), \
            f"File should exist at all times during atomic write, got: {file_existed_during_write}"

    def test_data_survives_replace_failure(self, store, tmp_path):
        """
        CORRECT behavior: if os.replace fails, original data should survive.

        With os.replace(), if the operation fails, the original file remains intact.
        os.replace() is atomic at the OS level - no partial state.
        """
        state_file = tmp_path / "execution-state.json"
        original_content = {"original": "data"}
        state_file.write_text(json.dumps(original_content), encoding="utf-8")

        def failing_replace(src, dst):
            raise OSError("Simulated replace failure")

        with patch('os.replace', failing_replace):
            with pytest.raises(OSError):
                store._atomic_write_json(state_file, {"new": "data"})

        # Original data should be intact
        content = json.loads(state_file.read_text(encoding="utf-8"))
        assert content == original_content, "Original data should survive failed atomic write"


class TestAtomicWritePatternAnalysis:
    """Analysis of the atomic write patterns."""

    def test_windows_rename_behavior_requires_replace_not_unlink_plus_rename(self):
        """
        On Windows, os.rename() fails if destination exists.
        On POSIX, os.rename() atomically overwrites.

        The unlink+rename pattern was added to "fix" Windows behavior but creates
        a data-loss window. The correct solution is os.replace() which:
        - Works atomically on both Windows and POSIX
        - Overwrites the destination if it exists
        - Never leaves a gap between delete and rename
        """
        # Document the correct solution
        assert hasattr(os, 'replace'), "os.replace() is available on Python 3.3+"