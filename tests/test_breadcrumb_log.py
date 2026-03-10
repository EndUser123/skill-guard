#!/usr/bin/env python3
"""
Test suite for append-only breadcrumb log

Acceptance Criteria:
- JSONL format, atomic writes, replay correctness, terminal isolation verified
"""

import json
import time

import pytest

from skill_guard.breadcrumb.log import AppendOnlyBreadcrumbLog, _get_log_file


class TestAppendOnlyBreadcrumbLog:
    """Test append-only breadcrumb log functionality."""

    def test_append_creates_jsonl_file(self):
        """Test that append creates JSONL file with correct format."""
        skill = "test_append_log"

        # Create log and append entry
        log = AppendOnlyBreadcrumbLog(skill)
        log.append({"event": "step_complete", "step": "analyze"})

        # Verify file exists
        log_file = _get_log_file(skill)
        assert log_file.exists()

        # Verify JSONL format (one JSON object per line)
        content = log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["event"] == "step_complete"
        assert entry["step"] == "analyze"
        assert "timestamp" in entry
        assert entry["skill"] == skill

    def test_append_multiple_entries(self):
        """Test appending multiple log entries."""
        skill = "test_multi_log"

        log = AppendOnlyBreadcrumbLog(skill)
        log.append({"event": "step_complete", "step": "analyze"})
        log.append({"event": "step_complete", "step": "refactor"})
        log.append({"event": "step_complete", "step": "test"})

        # Replay entries
        entries = log.replay()

        # Should return 3 entries in reverse order (newest first)
        assert len(entries) == 3
        assert entries[0]["step"] == "test"
        assert entries[1]["step"] == "refactor"
        assert entries[2]["step"] == "analyze"

    def test_replay_returns_newest_first(self):
        """Test that replay returns entries newest first."""
        skill = "test_chronological"

        log = AppendOnlyBreadcrumbLog(skill)

        # Append entries with known timestamps
        log.append({"event": "step1"})
        time.sleep(0.01)  # Small delay to ensure different timestamps
        log.append({"event": "step2"})
        time.sleep(0.01)
        log.append({"event": "step3"})

        # Replay should return newest first
        entries = log.replay()
        assert len(entries) == 3
        assert entries[0]["event"] == "step3"
        assert entries[1]["event"] == "step2"
        assert entries[2]["event"] == "step1"

    def test_replay_empty_when_no_file(self):
        """Test that replay returns empty list when log file doesn't exist."""
        skill = "test_nonexistent_log"

        log = AppendOnlyBreadcrumbLog(skill)
        entries = log.replay()

        assert entries == []

    def test_replay_handles_malformed_lines(self):
        """Test that replay skips malformed lines gracefully."""
        skill = "test_malformed_log"

        log = AppendOnlyBreadcrumbLog(skill)

        # Manually create log file with some malformed lines
        log_file = _get_log_file(skill)
        log_file.write_text(
            '{"event": "valid1", "step": "analyze"}\n'
            'invalid json line\n'
            '{"event": "valid2", "step": "refactor"}\n'
            'also not json\n'
            '{"event": "valid3", "step": "test"}\n'
        )

        # Replay should skip malformed lines
        entries = log.replay()
        assert len(entries) == 3
        assert entries[0]["event"] == "valid3"
        assert entries[1]["event"] == "valid2"
        assert entries[2]["event"] == "valid1"

    def test_append_augments_with_metadata(self):
        """Test that append adds timestamp and skill to entries."""
        skill = "test_metadata"

        log = AppendOnlyBreadcrumbLog(skill)
        before_time = time.time()

        log.append({"event": "custom", "data": "value"})

        after_time = time.time()

        entries = log.replay()
        assert len(entries) == 1

        entry = entries[0]
        assert "timestamp" in entry
        assert before_time <= entry["timestamp"] <= after_time
        assert entry["skill"] == skill
        assert entry["event"] == "custom"
        assert entry["data"] == "value"

    def test_clear_removes_log_file(self):
        """Test that clear removes the log file."""
        skill = "test_clear_log"

        log = AppendOnlyBreadcrumbLog(skill)
        log.append({"event": "step1"})

        # Verify file exists
        log_file = _get_log_file(skill)
        assert log_file.exists()

        # Clear log
        log.clear()

        # Verify file is gone
        assert not log_file.exists()

    def test_clear_on_nonexistent_file(self):
        """Test that clear doesn't error when file doesn't exist."""
        skill = "test_clear_nonexistent"

        log = AppendOnlyBreadcrumbLog(skill)

        # Should not raise exception
        log.clear()

        assert not _get_log_file(skill).exists()

    def test_path_traversal_blocked(self):
        """Test that path traversal characters are blocked."""
        malicious_names = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "test.file",
            "test..file",
        ]

        for malicious_name in malicious_names:
            with pytest.raises(ValueError, match="path traversal"):
                AppendOnlyBreadcrumbLog(malicious_name)

    def test_terminal_scoped_paths(self):
        """Test that log paths are terminal-scoped."""
        from skill_guard.utils.terminal_detection import detect_terminal_id

        skill = "test_terminal_scoped"
        log = AppendOnlyBreadcrumbLog(skill)

        terminal_id = detect_terminal_id()

        # Log file path should include terminal_id
        log_path_str = str(log.log_file)
        assert f"breadcrumb_logs_{terminal_id}" in log_path_str
        assert f"{skill}.jsonl" in log_path_str

    def test_concurrent_logs_dont_interfere(self):
        """Test that different skills have separate log files."""
        log1 = AppendOnlyBreadcrumbLog("skill1")
        log2 = AppendOnlyBreadcrumbLog("skill2")

        log1.append({"event": "step1"})
        log2.append({"event": "step2"})

        # Each log should only have its own entries
        entries1 = log1.replay()
        entries2 = log2.replay()

        assert len(entries1) == 1
        assert entries1[0]["event"] == "step1"

        assert len(entries2) == 1
        assert entries2[0]["event"] == "step2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
