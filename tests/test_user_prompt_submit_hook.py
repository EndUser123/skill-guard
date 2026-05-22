"""Tests for user_prompt_submit_hook.py"""

import pytest
from unittest.mock import MagicMock, patch

from skill_guard.user_prompt_submit_hook import (
    handle_user_prompt_submit,
    _NON_SKILL_COMMANDS,
    _map_contract_type,
)
from skill_guard.execution_run import ExecutionRun


class TestNonSkillCommandsNotBlocked:
    """
    INVARIANT 2 (UPS creates the run) - negative cases.

    Fact: Non-skill slash commands do not trigger run creation.
    """

    @pytest.mark.parametrize("cmd", sorted(_NON_SKILL_COMMANDS))
    def test_non_skill_command_returns_continue_true(self, cmd):
        """Non-skill commands are passthrough — no run created."""
        data = {"prompt": f"/{cmd} some args", "session_id": "s1"}
        result = handle_user_prompt_submit(data)
        assert result.get("continue") is True


class TestSkillDetection:
    """Test /skill-name detection and run creation."""

    @pytest.fixture
    def mock_runtime(self):
        runtime = MagicMock()
        run = ExecutionRun.new(
            skill_name="test", contract_type="workflow-execution",
            terminal_id="t1", session_id="s1",
        )
        runtime.create_run.return_value = run
        return runtime

    def test_prompt_without_slash_returns_continue(self):
        """Plain text prompt (no /skill-name) → pass through."""
        data = {"prompt": "just a question", "session_id": "s1"}
        result = handle_user_prompt_submit(data)
        assert result.get("continue") is True

    def test_skill_invocation_creates_run(self):
        """Explicit /skill-name → creates execution-state.json via create_run."""
        with patch("skill_guard.user_prompt_submit_hook.ExecutionRuntime") as MockRuntime:
            run = ExecutionRun.new(
                skill_name="gto", contract_type="workflow-execution",
                terminal_id="t1", session_id="s1",
            )
            mock_runtime = MagicMock()
            mock_runtime.create_run.return_value = run
            MockRuntime.return_value = mock_runtime

            data = {"prompt": "/gto analyze foo", "session_id": "s1"}
            result = handle_user_prompt_submit(data)

            # Enforcement fires for a real skill — result carries additionalContext
            assert "additionalContext" in result
            mock_runtime.create_run.assert_called()
            call_kwargs = mock_runtime.create_run.call_args[1]
            assert call_kwargs["skill_name"] == "gto"
            assert call_kwargs["contract_type"] == "workflow-execution"

    def test_fail_open_on_run_creation_error(self):
        """Run creation failure → tools still allowed (fail-open); enforcement still fires."""
        with patch("skill_guard.user_prompt_submit_hook.ExecutionRuntime") as MockRuntime:
            MockRuntime.side_effect = OSError("disk full")

            data = {"prompt": "/gto analyze foo", "session_id": "s1"}
            result = handle_user_prompt_submit(data)

            # Fail-open: no blocking stop reason even on run creation error
            assert "stopReason" not in result


class TestContractTypeDerivation:
    """
    INVARIANT 6 (contract type derived from SKILL.md) tests.

    Fact: _map_contract_type() maps skill config values to ExecutionRun contract_type.
    """

    def test_workflow_maps_to_workflow_execution(self):
        assert _map_contract_type("workflow") == "workflow-execution"

    def test_output_maps_to_structured_output(self):
        assert _map_contract_type("output") == "structured-output"

    def test_hybrid_maps_to_hybrid(self):
        assert _map_contract_type("hybrid") == "hybrid"

    def test_analysis_defaults_to_workflow_execution(self):
        assert _map_contract_type("analysis") == "workflow-execution"

    def test_unknown_defaults_to_workflow_execution(self):
        assert _map_contract_type("unknown-type") == "workflow-execution"
