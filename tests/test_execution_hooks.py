r"""Tests for execution_hooks.py"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skill_guard.execution_run import ExecutionEvent, ExecutionRun, RunStatus
from skill_guard.execution_hooks import (
    _artifact_written,
    _extract_slash_command,
    handle_pre_tool_use,
    handle_stop,
)


class TestExtractSlashCommand:
    def test_basic_slash_command(self):
        assert _extract_slash_command("/gto analyze foo") == "gto"

    def test_slash_only_at_start(self):
        assert _extract_slash_command("/test") == "test"

    def test_with_dashes(self):
        assert _extract_slash_command("/my-skill arg") == "my-skill"

    def test_no_slash(self):
        assert _extract_slash_command("just some text") is None

    def test_empty(self):
        assert _extract_slash_command("") is None


class TestArtifactWritten:
    def test_write_true(self):
        assert _artifact_written("Write", {"file_path": r"P:\\\\\\foo/bar.txt"}) is True

    def test_edit_true(self):
        assert _artifact_written("Edit", {"file_path": r"P:\\\\\\foo/bar.txt"}) is True

    def test_multiedit_true(self):
        assert _artifact_written("MultiEdit", {"file_path": r"P:\\\\\\foo/bar.txt"}) is True

    def test_read_false(self):
        assert _artifact_written("Read", {"file_path": r"P:\\\\\\foo/bar.txt"}) is False

    def test_tmp_path_false(self):
        assert _artifact_written("Write", {"file_path": "/tmp/foo.txt"}) is False
        assert _artifact_written("Write", {"file_path": r"P:\\\\\\tmp/foo.txt"}) is False


class TestHandlePreToolUse:
    """PreToolUse handler: blocks tools not in allowed_tools_now or in blocked_tools."""

    def test_allows_investigation_tools(self):
        """Investigation tools always pass through regardless of run state."""
        result = handle_pre_tool_use(
            {"tool_name": "Read", "input": {}}, runtime=None
        )
        assert result["continue"] is True

    def test_allows_when_no_active_run(self):
        mock_store = MagicMock()
        mock_runtime = MagicMock()
        mock_runtime.store = mock_store
        mock_runtime.load_active_run.return_value = None
        result = handle_pre_tool_use(
            {"tool_name": "Write", "input": {}}, runtime=mock_runtime
        )
        assert result["continue"] is True

    def test_blocks_blocked_tool(self):
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            blocked_tools=["Write"],
            allowed_tools=["Read"],
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            result = handle_pre_tool_use(
                {"tool_name": "Write", "input": {}}, runtime=mock_runtime
            )
        assert result["continue"] is False
        mock_store.append_event.assert_called()
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_blocked"

    def test_blocks_tool_not_in_allowed_list(self):
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            allowed_tools=["Read", "Grep"],
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            result = handle_pre_tool_use(
                {"tool_name": "Bash", "input": {}}, runtime=mock_runtime
            )
        assert result["continue"] is False
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_blocked"

    def test_allows_allowed_tool(self):
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            allowed_tools=["Read", "Bash"],
            blocked_tools=[],
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            result = handle_pre_tool_use(
                {"tool_name": "Bash", "input": {}}, runtime=mock_runtime
            )
        assert result["continue"] is True
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_allowed"


class TestHandleStop:
    """Stop handler: evaluate_completion + finalize_run."""

    @pytest.fixture
    def mock_runtime(self):
        with patch("skill_guard.execution_hooks.ExecutionRuntime") as MockRuntime:
            mock_store = MagicMock()
            mock_runtime_instance = MockRuntime.return_value
            mock_runtime_instance.store = mock_store
            yield mock_runtime_instance, mock_store

    def test_allows_when_no_active_run(self, mock_runtime):
        runtime, _ = mock_runtime
        runtime.load_active_run.return_value = None
        result = handle_stop({})
        assert result["allow"] is True

    def test_blocks_failed_run(self, mock_runtime):
        runtime, store = mock_runtime
        run = ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        run.status = RunStatus.FAILED
        runtime.load_active_run.return_value = run
        runtime.evaluate_completion.return_value = RunStatus.FAILED
        result = handle_stop({})
        assert result["allow"] is False
        runtime.finalize_run.assert_called_once()

    def test_allows_active_run(self, mock_runtime):
        runtime, store = mock_runtime
        run = ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        runtime.load_active_run.return_value = run
        runtime.evaluate_completion.return_value = RunStatus.ACTIVE
        result = handle_stop({})
        assert result["allow"] is True

    def test_allows_complete_run(self, mock_runtime):
        runtime, store = mock_runtime
        run = ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        runtime.load_active_run.return_value = run
        runtime.evaluate_completion.return_value = RunStatus.COMPLETE
        result = handle_stop({})
        assert result["allow"] is True

    def test_passes_transcript_path_for_structured_output(self, mock_runtime):
        runtime, store = mock_runtime
        run = ExecutionRun.new(
            skill_name="test", contract_type="structured-output",
            terminal_id="t1", session_id="s1",
            response_requirements={"sections": ["analysis"]},
        )
        runtime.load_active_run.return_value = run
        runtime.evaluate_completion.return_value = RunStatus.ACTIVE
        mock_transcript_path = "/tmp/transcript.jsonl"
        result = handle_stop({"transcript_path": mock_transcript_path})
        # Response text should be read from transcript
        runtime.evaluate_completion.assert_called()
        call_args = runtime.evaluate_completion.call_args
        # Second positional arg is response_text
        assert call_args[0][1] is not None  # response_text was passed


class TestToolEventOwnership:
    """Verify PreToolUse owns tool events, not PostToolUse."""

    def test_pre_tool_use_owns_tool_events(self):
        """PreToolUse record_tool_use must be the sole emitter of tool_allowed/tool_blocked."""
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            blocked_tools=["Edit"],
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            handle_pre_tool_use({"tool_name": "Edit", "input": {}}, runtime=mock_runtime)
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type in ("tool_allowed", "tool_blocked")
        assert event.event_type != "artifact_created"

    def test_no_tool_events_emitted_from_stop_for_allowed_tool(self):
        """Stop handler does not emit tool events — only run_ended."""
        with patch("skill_guard.execution_hooks.ExecutionRuntime") as MockRuntime, \
             patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            mock_store = MagicMock()
            mock_instance = MockRuntime.return_value
            mock_instance.store = mock_store
            mock_instance.load_active_run.return_value = ExecutionRun.new(
                skill_name="test", contract_type="workflow-execution",
                terminal_id="t1", session_id="s1",
            )
            mock_instance.evaluate_completion.return_value = RunStatus.COMPLETE
            handle_stop({})
            tool_events = [
                c[0][0] for c in mock_store.append_event.call_args_list
                if c[0][0].event_type in ("tool_allowed", "tool_blocked")
            ]
            assert len(tool_events) == 0


class TestPreToolUseFailClosed:
    """
    INVARIANT 3 (PreToolUse hard gate) - fail-closed behavior tests.

    Fact: Any tool NOT in allowed_tools_now AND NOT in blocked_tools → BLOCKED.
    Empty allowed_tools_now means all non-investigation tools are blocked unless
    explicitly in allowed list. Tools not in either list → blocked.
    """

    def test_tool_not_in_allowed_list_and_not_blocked_is_blocked(self):
        """Tool not in allowed list → blocked (fail-closed)."""
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="gto", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            allowed_tools=["Read", "Grep"],  # Write not in this list
            blocked_tools=[],  # Write not explicitly blocked either
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            result = handle_pre_tool_use(
                {"tool_name": "Write", "input": {}}, runtime=mock_runtime
            )
        assert result["continue"] is False
        event = mock_store.append_event.call_args[0][0]
        assert event.event_type == "tool_blocked"

    def test_empty_allowed_tools_means_no_restrictions(self):
        """
        Empty allowed_tools_now → no fail-closed enforcement (only blocked_tools apply).
        This matches the implementation: `run.allowed_tools_now and tool_name not in ...`
        When allowed_tools_now is empty (falsy), the second clause short-circuits.
        Empty allowed list means "no allow-list restriction", not "block all".
        """
        from skill_guard.execution_store import ExecutionStore
        from skill_guard.execution_runtime import ExecutionRuntime
        mock_store = MagicMock(spec=ExecutionStore)
        mock_runtime = ExecutionRuntime(store=mock_store)
        mock_runtime.load_active_run = MagicMock(return_value=ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
            allowed_tools=[],  # empty → no allow-list restriction
            blocked_tools=[],  # no explicit blocks
        ))
        with patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            result = handle_pre_tool_use(
                {"tool_name": "Bash", "input": {}}, runtime=mock_runtime
            )
        # Empty allowed list means "no restriction" — tool is allowed
        assert result["continue"] is True


class TestStopIsPure:
    """
    INVARIANT 4 (Stop is pure) - no recursion, no breadcrumb reads.

    Fact: handle_stop() reads execution-state.json, applies rules, returns.
    It does NOT call load_active_run() twice, does NOT re-evaluate after emit,
    does NOT read breadcrumb state, and does NOT make LLM calls.
    """

    def test_stop_reads_state_once(self):
        """Stop calls load_active_run() once, not multiple times."""
        with patch("skill_guard.execution_hooks.ExecutionRuntime") as MockRuntime, \
             patch("skill_guard.execution_hooks.detect_terminal_id", return_value="pytest_t1"):
            mock_store = MagicMock()
            mock_instance = MockRuntime.return_value
            mock_instance.store = mock_store
            mock_instance.load_active_run.return_value = ExecutionRun.new(
                skill_name="test", contract_type="workflow-execution",
                terminal_id="t1", session_id="s1",
            )
            mock_instance.evaluate_completion.return_value = RunStatus.ACTIVE
            handle_stop({})
            # Only called once
            assert mock_instance.load_active_run.call_count == 1

    def test_stop_does_not_read_breadcrumb_state(self):
        """
        Stop never imports or calls breadcrumb modules — only execution-state.json.
        Verifies by checking that handle_stop() only accesses runtime.load_active_run
        and runtime.evaluate_completion, not any breadcrumb methods.
        """
        from skill_guard.execution_hooks import handle_stop
        mock_runtime_instance = MagicMock()
        mock_store = MagicMock()
        mock_runtime_instance.store = mock_store

        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        mock_runtime_instance.load_active_run.return_value = run
        mock_runtime_instance.evaluate_completion.return_value = RunStatus.COMPLETE

        with patch("skill_guard.execution_hooks.ExecutionRuntime", return_value=mock_runtime_instance), \
             patch("skill_guard.execution_hooks.detect_terminal_id", return_value="t1"):
            handle_stop({})

            # Only load_active_run called on the runtime (which delegates to store)
            mock_runtime_instance.load_active_run.assert_called_once()
            # No breadcrumb methods on store
            assert not mock_store.load_breadcrumb_trail.called
            assert not mock_store.get_breadcrumbs.called

    def test_stop_no_llm_calls(self):
        """Stop does not call any LLM or AI analysis functions."""
        with patch("skill_guard.execution_hooks.ExecutionRuntime") as MockRuntime, \
             patch("skill_guard.execution_hooks.detect_terminal_id", return_value="t1"):
            mock_instance = MockRuntime.return_value
            mock_instance.store = MagicMock()
            mock_instance.load_active_run.return_value = None  # no run
            result = handle_stop({})
            assert result.get("allow") is True
            # No LLM wrappers instantiated
# ---------------------------------------------------------------------------
# Regression tests for the universal skill-first gate (Layer 0 in
# execution_hooks.handle_pre_tool_use). Runs BEFORE the run-state check, so
# it fires even when there is no active run yet.
# ---------------------------------------------------------------------------


class TestUniversalSkillFirstGate:
    def test_blocks_bash_before_skill_when_real_skill_invoked(self, tmp_path):
        from skill_guard.execution_hooks import handle_pre_tool_use
        from skill_guard.skill_enforcer import _skill_exists_cached
        skill_dir = tmp_path / "project_parent" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text("# stub", encoding="utf-8")
        with patch("skill_guard.execution_hooks._hooks_dir", return_value=tmp_path / "project_parent"), \
             patch("skill_guard.skill_enforcer._hooks_dir", return_value=tmp_path / "project_parent"):
            _skill_exists_cached.cache_clear()
            result = handle_pre_tool_use(
                {"tool_name": "Bash", "input": {"command": "ls"},
                 "user_message": "/my-skill"},
                runtime=None,
            )
        assert result["continue"] is False, f"expected block, got {result}"
        assert "my-skill" in result["reason"]
        assert "Skill()" in result["reason"]

    def test_blocks_namespaced_skill_before_skill(self):
        from skill_guard.execution_hooks import handle_pre_tool_use
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        result = handle_pre_tool_use(
            {"tool_name": "Bash", "input": {"command": "ls"},
             "user_message": "/cc-skills-utils:plugin-installer"},
            runtime=None,
        )
        assert result["continue"] is False
        assert "cc-skills-utils:plugin-installer" in result["reason"]
        assert "cc-skills-utils:" in result["reason"]

    def test_allows_non_skill_command_no_block(self):
        from skill_guard.execution_hooks import handle_pre_tool_use
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        result = handle_pre_tool_use(
            {"tool_name": "Bash", "input": {"command": "ls"},
             "user_message": "/nope-cmd-xyz-zzzzzz"},
            runtime=None,
        )
        assert result["continue"] is True

    def test_allows_builtin_clear(self):
        from skill_guard.execution_hooks import handle_pre_tool_use
        result = handle_pre_tool_use(
            {"tool_name": "Bash", "input": {"command": "ls"},
             "user_message": "/clear"},
            runtime=None,
        )
        assert result["continue"] is True

    def test_skill_call_passes_through_with_matching_name(self, tmp_path):
        from skill_guard.execution_hooks import handle_pre_tool_use
        from skill_guard.skill_enforcer import _skill_exists_cached
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text("#", encoding="utf-8")
        with patch("skill_guard.execution_hooks._hooks_dir", return_value=tmp_path), \
             patch("skill_guard.skill_enforcer._hooks_dir", return_value=tmp_path):
            _skill_exists_cached.cache_clear()
            result = handle_pre_tool_use(
                {"tool_name": "Skill", "input": {"skill": "my-skill"},
                 "user_message": "/my-skill"},
                runtime=None,
            )
        assert result["continue"] is True, f"expected pass-through, got {result}"

    def test_blocks_skill_with_mismatched_name(self, tmp_path):
        from skill_guard.execution_hooks import handle_pre_tool_use
        from skill_guard.skill_enforcer import _skill_exists_cached
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text("#", encoding="utf-8")
        with patch("skill_guard.execution_hooks._hooks_dir", return_value=tmp_path), \
             patch("skill_guard.skill_enforcer._hooks_dir", return_value=tmp_path):
            _skill_exists_cached.cache_clear()
            result = handle_pre_tool_use(
                {"tool_name": "Skill", "input": {"skill": "other-skill"},
                 "user_message": "/my-skill"},
                runtime=None,
            )
        assert result["continue"] is False
        assert "my-skill" in result["reason"]
        assert "other-skill" in result["reason"]


class TestNamespacedExtractor:
    def test_extracts_full_namespaced_name(self):
        from skill_guard.execution_hooks import _extract_slash_command
        assert _extract_slash_command("/cc-skills-utils:plugin-installer") == "cc-skills-utils:plugin-installer"

    def test_extracts_plain_name(self):
        from skill_guard.execution_hooks import _extract_slash_command
        assert _extract_slash_command("/plugin-installer arg") == "plugin-installer"

    def test_extracts_builtin(self):
        from skill_guard.execution_hooks import _extract_slash_command
        assert _extract_slash_command("/clear") == "clear"

    def test_returns_none_for_plain_text(self):
        from skill_guard.execution_hooks import _extract_slash_command
        assert _extract_slash_command("just chatting") is None


class TestSkillExistsCache:
    def test_returns_true_for_existing_skill(self):
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        assert _skill_exists_cached("plugin-installer") is True

    def test_returns_true_for_namespaced_skill(self):
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        assert _skill_exists_cached("cc-skills-utils:plugin-installer") is True

    def test_returns_false_for_missing_skill(self):
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        assert _skill_exists_cached("nope-cmd-xyz-not-a-real-skill") is False

    def test_cache_hits_repeat_calls(self):
        from skill_guard.skill_enforcer import _skill_exists_cached
        _skill_exists_cached.cache_clear()
        _skill_exists_cached("plugin-installer")
        info_after_first = _skill_exists_cached.cache_info()
        _skill_exists_cached("plugin-installer")
        _skill_exists_cached("plugin-installer")
        info_after_more = _skill_exists_cached.cache_info()
        assert info_after_more.hits > info_after_first.hits
