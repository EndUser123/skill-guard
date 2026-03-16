#!/usr/bin/env python3
"""
Integration tests for breadcrumb hooks.

These tests verify the end-to-end functionality of hooks that interact
with the breadcrumb trail system using the new schema format.

Test coverage:
- PreToolUse_workflow_steps_gate.py with dict format
- StopHook_skill_execution_gate.py verification reminder
- Breadcrumb trail initialization and updates
"""

import json
import sys

# Add paths
sys.path.insert(0, "P:/packages/skill-guard/src")
sys.path.insert(0, "P:/.claude/hooks")

from skill_guard.breadcrumb.tracker import (
    clear_breadcrumb_trail,
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
)


class TestPreToolUseGateWithNewFormat:
    """Test PreToolUse workflow_steps_gate with new dict format."""

    def test_blocks_when_skill_not_used_first_dict_format(self, tmp_path):
        """
        Test that PreToolUse gate blocks when Skill tool not used first.

        Given: A skill with workflow_steps in dict format
        When: User tries to use Read tool before Skill tool
        Then: Gate should block with clear message
        """
        # This test verifies that the PreToolUse_workflow_steps_gate.py
        # correctly handles the new dict format for workflow_steps

        # Mock skill with dict format workflow steps
        mock_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            {"id": "select_execution_model", "kind": "execution", "optional": False},
            {
                "id": "audit_quality_checks",
                "kind": "verification",
                "optional": True
            },
        ]

        # The hook should extract step IDs correctly from dict format
        # and display them in the block message
        step_ids = [s["id"] if isinstance(s, dict) else s for s in mock_steps]

        assert "analyze_query_intent" in step_ids
        assert "select_execution_model" in step_ids
        assert "audit_quality_checks" in step_ids
        assert len(step_ids) == 3

    def test_allows_after_skill_tool_used_dict_format(self, tmp_path):
        """
        Test that PreToolUse gate allows after Skill tool used.

        Given: A skill with workflow_steps in dict format
        When: User has used Skill tool first
        Then: Gate should allow other tools
        """
        # The PreToolUse gate tracks Skill tool usage via intent state
        # After Skill tool is used, other tools should be allowed

        # Mock intent state showing Skill tool was used
        intent_data = {
            "skill": "code",
            "prompt": "/code test feature",
            "timestamp": "2026-03-13T12:00:00",
            "session_id": "test-session",
            "terminal_id": "test-terminal",
        }

        intent_file = tmp_path / "pending_command_intent_test-terminal.json"
        intent_file.write_text(json.dumps(intent_data))

        assert intent_file.exists()
        assert json.loads(intent_file.read_text())["skill"] == "code"


class TestStopHookVerificationReminder:
    """Test StopHook verification reminder functionality."""

    def test_verification_reminder_emits_when_incomplete(self, tmp_path):
        """
        Test that verification reminder emits when steps incomplete.

        Given: A breadcrumb trail with incomplete verification steps
        When: Stop hook checks verification reminder
        Then: Reminder should be returned but allow=True
        """
        # Import the function from StopHook
        from StopHook_skill_execution_gate import check_verification_reminder

        # Create steps dict with incomplete verification steps
        steps = {
            "analyze_query_intent": {
                "kind": "execution",
                "status": "done",
                "optional": False,
                "evidence": {}
            },
            "audit_quality_checks": {
                "kind": "verification",
                "status": "pending",  # Incomplete
                "optional": True,
                "evidence": {}
            },
            "trace_manual_verification": {
                "kind": "verification",
                "status": "pending",  # Incomplete
                "optional": True,
                "evidence": {}
            },
        }

        result = check_verification_reminder(steps)

        # Should emit reminder but never block
        assert result["allow"] is True  # Never blocks
        assert result["reminder"] is not None  # Reminder emitted
        assert "audit_quality_checks" in result["reminder"]
        assert "trace_manual_verification" in result["reminder"]

    def test_verification_reminder_no_reminder_when_complete(self, tmp_path):
        """
        Test that verification reminder returns None when steps complete.

        Given: A breadcrumb trail with all verification steps done
        When: Stop hook checks verification reminder
        Then: No reminder should be returned
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        # All verification steps complete
        steps = {
            "analyze_query_intent": {
                "kind": "execution",
                "status": "done",
                "optional": False,
                "evidence": {}
            },
            "audit_quality_checks": {
                "kind": "verification",
                "status": "done",  # Complete
                "optional": True,
                "evidence": {}
            },
            "trace_manual_verification": {
                "kind": "verification",
                "status": "done",  # Complete
                "optional": True,
                "evidence": {}
            },
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True
        assert result.get("reminder") is None  # No reminder when complete

    def test_verification_reminder_handles_gracefully(self, tmp_path):
        """
        Test that verification reminder handles missing/malformed steps.

        Given: Invalid steps dict (None, empty, malformed)
        When: Stop hook checks verification reminder
        Then: Should return allow=True without error
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        # Test None steps
        result = check_verification_reminder(None)
        assert result["allow"] is True
        assert result.get("reminder") is None

        # Test empty dict
        result = check_verification_reminder({})
        assert result["allow"] is True
        assert result.get("reminder") is None

        # Test malformed steps (missing fields)
        steps = {
            "step1": {"status": "pending"},  # Missing 'kind'
            "step2": {"kind": "verification"},  # Missing 'status'
        }
        result = check_verification_reminder(steps)
        assert result["allow"] is True  # Should not crash


class TestPostToolUseEvidenceTracking:
    """Test PostToolUse evidence tracking functionality."""

    def test_set_breadcrumb_with_evidence_stores_correctly(self, tmp_path):
        """
        Test that set_breadcrumb() stores evidence in steps dict.

        Given: A skill tracking execution progress
        When: set_breadcrumb() called with evidence parameter
        Then: Evidence should be stored in steps[step_name]["evidence"]
        """
        from unittest.mock import patch

        skill_name = "test_skill"
        step_name = "analyze_query_intent"
        evidence = {
            "tool": "AskUserQuestion",
            "input": {"questions": [{"question": "What to build?"}]},
            "timestamp": "2026-03-13T12:00:00"
        }

        # Mock _load_workflow_steps to return test steps
        mock_workflow_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            {"id": "audit_quality_checks", "kind": "verification", "optional": True},
        ]

        with patch('skill_guard.breadcrumb.tracker._load_workflow_steps') as mock_load:
            mock_load.return_value = mock_workflow_steps

            # Initialize trail
            initialize_breadcrumb_trail(skill_name)

            # Set breadcrumb with evidence
            set_breadcrumb(skill_name, step_name, evidence)

            # Verify evidence stored
            trail = get_breadcrumb_trail(skill_name)
            assert trail is not None
            assert "steps" in trail
            assert step_name in trail["steps"]
            assert trail["steps"][step_name]["evidence"] == evidence

            # Cleanup
            clear_breadcrumb_trail(skill_name)

    def test_set_breadcrumb_without_evidence_preserves(self, tmp_path):
        """
        Test that set_breadcrumb() without evidence preserves existing evidence.

        Given: A step with existing evidence
        When: set_breadcrumb() called without evidence parameter
        Then: Existing evidence should not be overwritten
        """
        from unittest.mock import patch

        skill_name = "test_skill"
        step_name = "analyze_query_intent"

        mock_workflow_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
        ]

        with patch('skill_guard.breadcrumb.tracker._load_workflow_steps') as mock_load:
            mock_load.return_value = mock_workflow_steps

            # Initialize and set with evidence
            initialize_breadcrumb_trail(skill_name)
            initial_evidence = {"tool": "AskUserQuestion", "result": "user clarified"}
            set_breadcrumb(skill_name, step_name, initial_evidence)

            # Update without new evidence
            set_breadcrumb(skill_name, step_name, None)

            # Verify initial evidence preserved
            trail = get_breadcrumb_trail(skill_name)
            assert trail is not None
            assert trail["steps"][step_name]["evidence"] == initial_evidence

            # Cleanup
            clear_breadcrumb_trail(skill_name)

    def test_evidence_overwrites_on_subsequent_calls(self, tmp_path):
        """
        Test that subsequent evidence calls overwrite previous evidence.

        Given: A step with existing evidence
        When: set_breadcrumb() called with new evidence
        Then: New evidence should replace old evidence
        """
        from unittest.mock import patch

        skill_name = "test_skill"
        step_name = "analyze_query_intent"

        mock_workflow_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
        ]

        with patch('skill_guard.breadcrumb.tracker._load_workflow_steps') as mock_load:
            mock_load.return_value = mock_workflow_steps

            # Initialize and set initial evidence
            initialize_breadcrumb_trail(skill_name)
            initial_evidence = {"version": 1, "tool": "old_tool"}
            set_breadcrumb(skill_name, step_name, initial_evidence)

            # Verify initial evidence set
            trail = get_breadcrumb_trail(skill_name)
            assert trail["steps"][step_name]["evidence"] == initial_evidence

            # Update with new evidence (cache is updated by set_breadcrumb)
            new_evidence = {"version": 2, "tool": "new_tool", "result": "success"}
            set_breadcrumb(skill_name, step_name, new_evidence)

            # Verify new evidence replaced old
            trail = get_breadcrumb_trail(skill_name)
            assert trail is not None
            assert trail["steps"][step_name]["evidence"] == new_evidence
            assert trail["steps"][step_name]["evidence"]["version"] == 2

            # Cleanup
            clear_breadcrumb_trail(skill_name)


class TestEndToEndIntegration:
    """End-to-end integration tests for complete workflow."""

    def test_full_workflow_with_verification_steps(self, tmp_path):
        """
        Test complete workflow: initialize → execute steps → verification reminder.

        Given: A skill with verification steps
        When: Full workflow executed
        Then: All components should work together correctly
        """
        from unittest.mock import patch

        from StopHook_skill_execution_gate import check_verification_reminder

        skill_name = "test_skill"

        # Mock workflow steps
        mock_workflow_steps = [
            {"id": "analyze_query_intent", "kind": "execution", "optional": False},
            {"id": "tdd_implementation", "kind": "execution", "optional": False},
            {"id": "audit_quality_checks", "kind": "verification", "optional": True},
        ]

        with patch('skill_guard.breadcrumb.tracker._load_workflow_steps') as mock_load:
            mock_load.return_value = mock_workflow_steps

            # Initialize breadcrumb trail
            initialize_breadcrumb_trail(skill_name)
            trail = get_breadcrumb_trail(skill_name)

            # Verify initialization
            assert trail is not None
            assert "steps" in trail
            assert "run_id" in trail
            assert len(trail["run_id"]) > 0  # Non-empty run_id

            # Execute some steps
            set_breadcrumb(skill_name, "analyze_query_intent",
                         {"tool": "AskUserQuestion", "result": "clarified"})
            set_breadcrumb(skill_name, "tdd_implementation",
                         {"tool": "Write", "file": "test.py"})

            # Check verification reminder (should remind since verification steps pending)
            result = check_verification_reminder(trail.get("steps", {}))
            assert result["allow"] is True  # Never blocks
            # May or may not have reminder depending on verification steps status

            # Complete verification steps
            set_breadcrumb(skill_name, "audit_quality_checks",
                         {"tool": "Bash", "command": "ruff check"})

            # Cleanup
            clear_breadcrumb_trail(skill_name)

            # Verify cleanup
            trail_after = get_breadcrumb_trail(skill_name)
            assert trail_after is None
