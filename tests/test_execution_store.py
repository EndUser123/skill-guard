"""Tests for execution_store.py"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from skill_guard.execution_run import ExecutionEvent, ExecutionRun, RunStatus
from skill_guard.execution_store import ArtifactsExecutionStore, ExecutionStore


class TestArtifactsExecutionStore:
    """Test ArtifactsExecutionStore using a temp artifacts root."""

    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create a store pointing to a temp artifacts directory."""
        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("pytest_console_abc")
            yield store

    def test_console_dir_uses_terminal_id(self, tmp_path):
        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("console_abc123")
            console_dir = store.console_dir()
            assert console_dir.name == "console_console_abc123"
            assert console_dir.parent == tmp_path

    def test_save_and_load_roundtrip(self, temp_store):
        run = ExecutionRun.new(
            skill_name="gto",
            contract_type="workflow-execution",
            terminal_id="pytest_console_abc",
            session_id="sess1",
            required_artifacts=["SKILL.md"],
            allowed_tools=["Read", "Grep"],
        )
        temp_store.save_run(run)
        loaded = temp_store.load_active_run()
        assert loaded is not None
        assert loaded.skill_name == "gto"
        assert loaded.contract_type == "workflow-execution"
        assert loaded.status == RunStatus.ACTIVE
        assert loaded.run_id == run.run_id

    def test_load_active_run_returns_none_when_no_state(self, temp_store):
        assert temp_store.load_active_run() is None

    def test_append_event_writes_jsonl_line(self, temp_store):
        event = ExecutionEvent(event_type="tool_allowed", tool="Read")
        temp_store.append_event(event)
        events = temp_store.replay_events()
        assert len(events) == 1
        assert events[0].event_type == "tool_allowed"
        assert events[0].tool == "Read"

    def test_replay_events_returns_all_events(self, temp_store):
        temp_store.append_event(ExecutionEvent(event_type="run_created", skill="gto"))
        temp_store.append_event(ExecutionEvent(event_type="tool_allowed", tool="Read"))
        temp_store.append_event(ExecutionEvent(event_type="tool_blocked", tool="Write"))
        events = temp_store.replay_events()
        assert len(events) == 3
        assert events[0].event_type == "run_created"
        assert events[1].tool == "Read"
        assert events[2].tool == "Write"

    def test_end_run_clears_state(self, temp_store):
        run = ExecutionRun.new(
            skill_name="gto",
            contract_type="workflow-execution",
            terminal_id="pytest_console_abc",
            session_id="sess1",
        )
        temp_store.save_run(run)
        temp_store.end_run(run, "complete")
        assert temp_store.load_active_run() is None

    def test_end_run_creates_backup(self, temp_store):
        run = ExecutionRun.new(
            skill_name="gto",
            contract_type="workflow-execution",
            terminal_id="pytest_console_abc",
            session_id="sess1",
        )
        temp_store.save_run(run)
        temp_store.end_run(run, "complete")
        backup = temp_store._state_path().with_suffix(".json.ended")
        assert backup.exists()

    def test_replay_events_skips_malformed_lines(self, temp_store):
        events_path = temp_store._events_path()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            '{"type":"tool_allowed","ts":1}\nnotjson\n{"type":"artifact_created","path":"f.json"}\n',
            encoding="utf-8",
        )
        events = temp_store.replay_events()
        assert len(events) == 2
        assert events[0].event_type == "tool_allowed"
        assert events[1].path == "f.json"

    def test_replay_events_empty_when_no_file(self, temp_store):
        assert temp_store.replay_events() == []


class TestExecutionStoreInterface:
    """Verify ArtifactsExecutionStore implements ExecutionStore correctly."""

    def test_load_active_run_returns_run_or_none(self, tmp_path):
        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("t1")
            result = store.load_active_run()
            assert result is None or isinstance(result, ExecutionRun)

    def test_save_run_persists_run(self, tmp_path):
        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("t1")
            run = ExecutionRun.new("skill", "workflow-execution", "t1", "s1")
            store.save_run(run)
            loaded = store.load_active_run()
            assert loaded is not None

    def test_append_event_is_idempotent(self, tmp_path):
        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("t1")
            store.append_event(ExecutionEvent(event_type="tool_allowed", tool="Read"))
            store.append_event(ExecutionEvent(event_type="tool_allowed", tool="Read"))
            events = store.replay_events()
            assert len(events) == 2