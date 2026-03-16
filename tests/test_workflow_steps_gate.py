#!/usr/bin/env python3
"""
Test suite for PreToolUse_workflow_steps_gate.py hook.

These tests verify that the workflow_steps_gate correctly handles both
list[str] and list[dict] formats for workflow_steps.

Characterization tests for TASK-003: Update hook to handle new list[dict] format.
"""

import json
import sys
from unittest.mock import patch

# Add hooks directory to path for imports
sys.path.insert(0, "P:/.claude/hooks")
import PreToolUse_workflow_steps_gate as gate_module


class TestWorkflowStepsGateDictFormat:
    """Test handling of new list[dict] format for workflow_steps."""

    def test_dict_format_with_step_ids_extracted(self, tmp_path):
        """
        Test that dict format workflow_steps are handled correctly.

        Given: A skill with workflow_steps in dict format
        When: _load_workflow_steps returns list[dict]
        Then: Step IDs should be extracted for display in block message

        Example:
          workflow_steps = [
            {"id": "step1", "kind": "execution", "optional": False},
            {"id": "step2", "kind": "validation", "optional": True}
          ]
          Should extract: ["step1", "step2"]
        """
        # This test will FAIL until the hook is updated to handle dict format
        # The current code expects list[str] and will fail when given list[dict]

        # Mock the _load_workflow_steps to return dict format
        mock_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            {"id": "select_execution_model", "kind": "execution", "optional": False},
            {"id": "verify_results", "kind": "validation", "optional": True},
        ]

        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.return_value = mock_steps

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "code",
                "prompt": "/code test feature",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # The hook should block and show step IDs in the message
                    assert result is not None
                    assert result["continue"] is False

                    # Verify step IDs are extracted and displayed (this will FAIL with current code)
                    reason = result["reason"]
                    assert "analyze_query_intent" in reason
                    assert "select_execution_model" in reason

    def test_string_format_backward_compatibility(self, tmp_path):
        """
        Test that string format workflow_steps still work (backward compatibility).

        Given: A skill with workflow_steps in old string format
        When: _load_workflow_steps returns list[str]
        Then: Should work as before (no regression)

        Example:
          workflow_steps = ["step1", "step2", "step3"]
          Should display: step1, step2, step3
        """
        # Mock the _load_workflow_steps to return string format
        mock_steps = [
            "analyze_query_intent",
            "select_execution_model",
            "verify_results",
        ]

        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.return_value = mock_steps

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "code",
                "prompt": "/code test feature",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # The hook should block and show step names
                    assert result is not None
                    assert result["continue"] is False

                    # Verify step names are displayed
                    reason = result["reason"]
                    assert "analyze_query_intent" in reason
                    assert "select_execution_model" in reason

    def test_mixed_format_handled(self, tmp_path):
        """
        Test that mixed format (some dict, some string) is handled correctly.

        Given: A skill with mixed workflow_steps format
        When: _load_workflow_steps returns list with both str and dict
        Then: Should extract IDs from both formats correctly

        Example:
          workflow_steps = [
            {"id": "step1", "kind": "execution"},
            "step2",
            {"id": "step3", "optional": True}
          ]
          Should extract: ["step1", "step2", "step3"]
        """
        # Mock the _load_workflow_steps to return mixed format
        mock_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            "select_execution_model",  # String format
            {"id": "verify_results", "kind": "validation", "optional": True},
        ]

        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.return_value = mock_steps

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "code",
                "prompt": "/code test feature",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # The hook should block and show all step IDs
                    assert result is not None
                    assert result["continue"] is False

                    # Verify all step IDs are extracted
                    reason = result["reason"]
                    assert "analyze_query_intent" in reason
                    assert "select_execution_model" in reason
                    assert "verify_results" in reason

    def test_optional_and_kind_fields_preserved(self, tmp_path):
        """
        Test that optional and kind fields are accessible for validation logic.

        Given: A skill with dict format workflow_steps
        When: The hook processes workflow_steps
        Then: Optional and kind fields should be accessible for future validation

        Note: This test verifies the data structure supports these fields.
        The current implementation may not use them yet, but they should
        be accessible for future enhancement (e.g., skip optional steps).
        """
        # Mock the _load_workflow_steps to return dict format with metadata
        mock_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            {"id": "preflight_checks", "kind": "validation", "optional": True},
            {"id": "implement_solution", "kind": "execution", "optional": False},
        ]

        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.return_value = mock_steps

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "code",
                "prompt": "/code test feature",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # Verify the hook processes the steps
                    assert result is not None
                    assert result["continue"] is False

                    # The step count should reflect all steps
                    reason = result["reason"]
                    assert "3 declared workflow steps" in reason

                    # All step IDs should be visible
                    assert "analyze_query_intent" in reason
                    assert "preflight_checks" in reason
                    assert "implement_solution" in reason


class TestWorkflowStepsGateEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_workflow_steps_allows_tool(self, tmp_path):
        """
        Test that empty workflow_steps allows tool usage (knowledge skill).

        Given: A skill with no workflow_steps (knowledge skill)
        When: _load_workflow_steps returns empty list
        Then: Should not block (allow prose responses)
        """
        # Mock the _load_workflow_steps to return empty list
        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.return_value = []

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "knowledge",  # Knowledge skill has no workflow_steps
                "prompt": "/knowledge explain something",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # Should not block (knowledge skill)
                    assert result is None

    def test_skill_tool_allowed(self):
        """
        Test that Skill tool is always allowed (bypasses workflow_steps check).

        Given: User attempts to use Skill tool
        When: tool_name is "Skill"
        Then: Should not block regardless of workflow_steps
        """
        # Mock terminal detection
        with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
            mock_terminal.return_value = "test_terminal"

            # Test data for Skill tool
            hook_data = {
                "tool_name": "Skill",
                "session": {"id": "test-session-123"},
                "terminal_id": "test_terminal",
            }

            # Run the hook
            result = gate_module.run(hook_data)

            # Should not block (Skill tool always allowed)
            assert result is None

    def test_load_workflow_steps_exception_fails_open(self, tmp_path):
        """
        Test that exceptions in _load_workflow_steps fail open (don't block).

        Given: _load_workflow_steps raises an exception
        When: The hook catches the exception
        Then: Should fail open and allow the tool (safety mechanism)
        """
        # Mock the _load_workflow_steps to raise exception
        with patch("skill_guard.breadcrumb.tracker._load_workflow_steps") as mock_load:
            mock_load.side_effect = Exception("Simulated load failure")

            # Create test intent file
            intent_file = tmp_path / "pending_command_intent_test_terminal.json"
            intent_data = {
                "skill": "code",
                "prompt": "/code test feature",
                "timestamp": "2026-03-13T12:00:00",
                "session_id": "test-session-123",
                "terminal_id": "test_terminal",
            }
            intent_file.write_text(json.dumps(intent_data))

            # Mock the intent file path
            with patch.object(gate_module, "_get_intent_file") as mock_get_file:
                mock_get_file.return_value = intent_file

                # Mock terminal detection
                with patch.object(gate_module, "_get_terminal_id") as mock_terminal:
                    mock_terminal.return_value = "test_terminal"

                    # Test data for hook
                    hook_data = {
                        "tool_name": "Read",
                        "session": {"id": "test-session-123"},
                        "terminal_id": "test_terminal",
                    }

                    # Run the hook
                    result = gate_module.run(hook_data)

                    # Should fail open (allow tool) when exception occurs
                    assert result is None
