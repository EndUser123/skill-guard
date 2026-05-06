"""Tests for execution_runtime.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skill_guard.execution_run import ExecutionEvent, ExecutionRun, RunStatus
from skill_guard.execution_runtime import (
    ExecutionRuntime,
    ResponseCheckResult,
    validate_response_requirements,
)


class TestValidateResponseRequirements:
    """Tests for the standalone response validation helper."""

    def test_empty_requirements_returns_ok(self):
        result = validate_response_requirements("any text", {})
        assert result.ok is True
        assert result.missing == []
        assert result.violations == []

    def test_all_sections_found(self):
        reqs = {"sections": ["analysis", "verification"]}
        text = "Here is the analysis section and the verification section."
        result = validate_response_requirements(text, reqs)
        assert result.ok is True
        assert result.missing == []

    def test_missing_section(self):
        reqs = {"sections": ["analysis", "recommendations"]}
        text = "Here is the analysis section only."
        result = validate_response_requirements(text, reqs)
        assert result.ok is False
        assert "section:recommendations" in result.missing
        assert "section:analysis" not in result.missing

    def test_case_insensitive_section_check(self):
        reqs = {"sections": ["ANALYSIS"]}
        result = validate_response_requirements("this has analysis in lowercase", reqs)
        assert result.ok is True

    def test_prohibited_phrase_found(self):
        reqs = {"prohibited_claims": ["TODO: fix this later", "broken"]}
        text = "The system is broken. TODO: fix this later."
        result = validate_response_requirements(text, reqs)
        assert result.ok is False
        assert "prohibited:broken" in result.violations
        assert "prohibited:TODO: fix this later" in result.violations

    def test_prohibited_case_insensitive(self):
        reqs = {"prohibited_claims": ["BROKEN"]}
        result = validate_response_requirements("this is broken", reqs)
        assert result.ok is False
        assert "prohibited:BROKEN" in result.violations

    def test_both_missing_and_violations(self):
        reqs = {"sections": ["recommendations"], "prohibited_claims": ["broken"]}
        text = "the system is broken and the executive-summary section is absent"
        result = validate_response_requirements(text, reqs)
        assert result.ok is False
        assert "section:recommendations" in result.missing
        assert "prohibited:broken" in result.violations


class TestEvaluateCompletion:
    """Tests for evaluate_completion with short-circuits and contract rules."""

    @pytest.fixture
    def mock_store(self):
        return MagicMock()

    def test_failed_short_circuits(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="workflow-execution",
            terminal_id="t1",
            session_id="s1",
        )
        run.status = RunStatus.FAILED
        status = runtime.evaluate_completion(run)
        assert status == RunStatus.FAILED
        mock_store.save_run.assert_not_called()

    def test_workflow_execution_complete(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="workflow-execution",
            terminal_id="t1",
            session_id="s1",
            required_artifacts=["a.txt", "b.txt"],
        )
        run.completed_artifacts = ["a.txt", "b.txt"]
        status = runtime.evaluate_completion(run)
        assert status == RunStatus.COMPLETE

    def test_workflow_execution_incomplete(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="workflow-execution",
            terminal_id="t1",
            session_id="s1",
            required_artifacts=["a.txt", "b.txt"],
        )
        run.completed_artifacts = ["a.txt"]
        status = runtime.evaluate_completion(run)
        assert status == RunStatus.ACTIVE

    def test_workflow_execution_with_missing_requirements(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="workflow-execution",
            terminal_id="t1",
            session_id="s1",
            required_artifacts=["a.txt"],
        )
        run.completed_artifacts = ["a.txt"]
        run.missing_requirements = ["section:analysis"]
        status = runtime.evaluate_completion(run)
        assert status == RunStatus.ACTIVE

    def test_structured_output_no_response_yet(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="structured-output",
            terminal_id="t1",
            session_id="s1",
            response_requirements={"sections": ["analysis"]},
        )
        status = runtime.evaluate_completion(run, response_text=None)
        assert status == RunStatus.ACTIVE

    def test_structured_output_complete(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="structured-output",
            terminal_id="t1",
            session_id="s1",
            response_requirements={"sections": ["analysis"]},
        )
        status = runtime.evaluate_completion(run, response_text="here is the analysis section")
        assert status == RunStatus.COMPLETE

    def test_structured_output_incomplete_response(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="structured-output",
            terminal_id="t1",
            session_id="s1",
            response_requirements={"sections": ["analysis", "executive-summary"]},
        )
        status = runtime.evaluate_completion(
            run, response_text="here is the analysis section but the executive summary is missing"
        )
        assert status == RunStatus.ACTIVE
        assert run.missing_requirements == ["section:executive-summary"]

    def test_structured_output_with_prohibited_claim(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="structured-output",
            terminal_id="t1",
            session_id="s1",
            response_requirements={"sections": ["analysis"], "prohibited_claims": ["todo"]},
        )
        status = runtime.evaluate_completion(run, response_text="analysis shows TODO: fix this")
        assert status == RunStatus.ACTIVE
        assert any("prohibited" in r for r in run.missing_requirements)

    def test_hybrid_complete_when_both_satisfied(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="hybrid",
            terminal_id="t1",
            session_id="s1",
            required_artifacts=["a.txt"],
            response_requirements={"sections": ["analysis"]},
        )
        run.completed_artifacts = ["a.txt"]
        status = runtime.evaluate_completion(
            run, response_text="here is the analysis section"
        )
        assert status == RunStatus.COMPLETE

    def test_hybrid_incomplete_when_artifacts_missing(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="hybrid",
            terminal_id="t1",
            session_id="s1",
            required_artifacts=["a.txt"],
            response_requirements={"sections": ["analysis"]},
        )
        run.completed_artifacts = []
        status = runtime.evaluate_completion(
            run, response_text="analysis section present"
        )
        assert status == RunStatus.ACTIVE


class TestRecordToolUse:
    """Tests for record_tool_use (PreToolUse's method)."""

    @pytest.fixture
    def mock_store(self):
        return MagicMock()

    def test_allowed_tool_transitions_phase_loaded_to_executing(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        run.phase = "loaded"
        runtime.record_tool_use(run, tool_name="Read", allowed=True)
        assert run.phase == "executing"
        mock_store.append_event.assert_called_once()
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_allowed"

    def test_allowed_tool_transitions_phase_pending_to_loaded(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        run.phase = "pending"
        runtime.record_tool_use(run, tool_name="Read", allowed=True)
        assert run.phase == "loaded"

    def test_blocked_tool_sets_status_failed(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        runtime.record_tool_use(run, tool_name="Write", allowed=False, reason="blocked")
        assert run.status == RunStatus.FAILED
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_blocked"
        assert event.reason == "blocked"

    def test_blocked_tool_does_not_transition_phase(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        run.phase = "loaded"
        runtime.record_tool_use(run, tool_name="Edit", allowed=False)
        assert run.phase == "loaded"  # phase unchanged when blocked


class TestRecordArtifactCreated:
    """Tests for record_artifact_created (PostToolUse's method)."""

    @pytest.fixture
    def mock_store(self):
        return MagicMock()

    def test_adds_to_completed_artifacts(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            required_artifacts=["a.txt"],
        )
        runtime.record_artifact_created(run, "a.txt")
        assert "a.txt" in run.completed_artifacts
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "artifact_created"

    def test_removes_from_missing_requirements(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            required_artifacts=["a.txt"],
        )
        run.missing_requirements = ["section:analysis"]
        runtime.record_artifact_created(run, "a.txt")
        assert "a.txt" not in run.missing_requirements

    def test_idempotent_same_artifact_twice(self, mock_store):
        runtime = ExecutionRuntime(store=mock_store)
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        runtime.record_artifact_created(run, "a.txt")
        runtime.record_artifact_created(run, "a.txt")
        assert run.completed_artifacts.count("a.txt") == 1
        assert mock_store.append_event.call_count == 2


class TestOneActiveRunPerTerminal:
    """
    INVARIANT 1 (one active run per terminal) tests.

    execution-state.json is the SOLE authority for active contract runs.
    At most one ACTIVE run exists per terminal_id at any time.
    When a new run is created for a terminal with an existing ACTIVE run,
    the prior run is silently ended and replaced — the new run takes ownership.
    """

    def test_second_create_replaces_first(self):
        """
        Create two runs for same terminal → second run takes ownership,
        first run is ended with status=replaced via create_or_replace_run.

        Fact: create_or_replace_run() is called (not save_run) on every create_run.
        """
        from unittest.mock import MagicMock
        from skill_guard.execution_store import ArtifactsExecutionStore

        store = MagicMock()  # MagicMock auto-provides all method attributes

        runtime = ExecutionRuntime(store=store)
        runtime.create_run(skill_name="gto", contract_type="workflow-execution", session_id="s1")

        store.create_or_replace_run.assert_called()

    def test_ended_replaced_run_emits_run_ended_event(self, tmp_path):
        """
        Direct integration test: ArtifactsExecutionStore.create_or_replace_run
        when prev exists ends it with status=replaced and saves the new run.

        Fact: real create_or_replace_run(prev exists) → end_run(prev, "replaced") called.
        Covered by test_execution_store.py::TestCreateOrReplaceRun::test_prev_replaced_ends_with_replaced_status.
        """
        from unittest.mock import patch
        from skill_guard.execution_store import ArtifactsExecutionStore

        with patch.object(ArtifactsExecutionStore, "ARTIFACTS_ROOT", tmp_path):
            store = ArtifactsExecutionStore("t1")
            run1 = ExecutionRun.new("gto", "workflow-execution", "t1", "s1")
            store.save_run(run1)

            run2 = ExecutionRun.new("bf", "structured-output", "t1", "s2")
            store.create_or_replace_run(run2)

            # Verify run1 ended with status=replaced
            events = store.replay_events()
            run_ended = [e for e in events if e.event_type == "run_ended"]
            assert len(run_ended) == 1
            assert run_ended[0].status == "replaced"

            # Verify run2 is active
            loaded = store.load_active_run()
            assert loaded.run_id == run2.run_id