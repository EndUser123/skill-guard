"""
Failing tests for check_verification_reminder() function.

These tests verify the verification reminder functionality for TASK-004.
Run with: pytest P:/packages/skill-guard/tests/test_verification_reminder.py -v

Function specification:
- Location: P:/.claude/hooks/StopHook_skill_execution_gate.py
- Filters steps by kind=verification, status!=done
- Returns {"allow": True, "reminder": "..."}
- Warn-only (never blocks)
- Optional steps: audit_quality_checks, trace_manual_verification, done_final_certification
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Add hooks directory to path for importing
HOOKS_DIR = Path("P:/.claude/hooks")
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


# Test helpers
def create_step(
    step_id: str,
    kind: str = "verification",
    status: str = "pending"
) -> Dict[str, Any]:
    """Create a step dict for testing."""
    return {
        "step_id": step_id,
        "kind": kind,
        "status": status
    }


class TestCheckVerificationReminderFunctionExists:
    """Test that the function exists and has correct signature."""

    def test_function_exists(self):
        """
        Test that check_verification_reminder function exists in StopHook_skill_execution_gate.

        Given: StopHook_skill_execution_gate module is imported
        When: We try to access check_verification_reminder function
        Then: Function should exist and be callable
        """
        # This will fail until function is implemented
        try:
            from StopHook_skill_execution_gate import check_verification_reminder
            assert callable(check_verification_reminder), "Function should be callable"
        except (ImportError, AttributeError) as e:
            pytest.fail(f"check_verification_reminder function not found: {e}")

    def test_function_accepts_steps_dict(self):
        """
        Test that function accepts steps dict parameter.

        Given: Function is defined
        When: Called with steps dict
        Then: Should not raise TypeError
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "step1": create_step("step1", kind="verification", status="pending")
        }

        # Should not raise
        result = check_verification_reminder(steps)
        assert isinstance(result, dict), "Should return dict"


class TestVerificationStepFiltering:
    """Test filtering of verification steps."""

    def test_filters_by_kind_verification(self):
        """
        Test that only steps with kind=verification are checked.

        Given: Steps dict with mixed kinds
        When: check_verification_reminder is called
        Then: Only verification steps should be considered for reminders
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "step1": create_step("step1", kind="verification", status="pending"),
            "step2": create_step("step2", kind="execution", status="pending"),
            "step3": create_step("step3", kind="verification", status="done"),
        }

        result = check_verification_reminder(steps)

        # Should return reminder for pending verification step
        assert result["allow"] is True, "Should always allow"
        assert "reminder" in result, "Should have reminder key"
        assert "step1" in result["reminder"] or "verification" in result["reminder"].lower()

    def test_ignores_non_verification_steps(self):
        """
        Test that non-verification steps are ignored.

        Given: Steps dict with only execution kind steps
        When: check_verification_reminder is called
        Then: No reminder should be returned
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "step1": create_step("step1", kind="execution", status="pending"),
            "step2": create_step("step2", kind="planning", status="pending"),
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True
        # No reminder needed for non-verification steps
        assert result.get("reminder") == "" or result.get("reminder") is None


class TestStatusNotDoneFiltering:
    """Test filtering by status != done."""

    def test_reminds_on_pending_status(self):
        """
        Test that pending verification steps trigger reminder.

        Given: Verification step with status=pending
        When: check_verification_reminder is called
        Then: Reminder should be returned
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "audit_quality_checks": create_step(
                "audit_quality_checks",
                kind="verification",
                status="pending"
            ),
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True, "Should always allow (warn-only)"
        assert "reminder" in result
        assert len(result["reminder"]) > 0, "Reminder should not be empty"

    def test_reminds_on_in_progress_status(self):
        """
        Test that in-progress verification steps trigger reminder.

        Given: Verification step with status=in_progress
        When: check_verification_reminder is called
        Then: Reminder should be returned
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "trace_manual_verification": create_step(
                "trace_manual_verification",
                kind="verification",
                status="in_progress"
            ),
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True, "Should always allow"
        assert "reminder" in result
        assert len(result["reminder"]) > 0

    def test_no_reminder_for_done_status(self):
        """
        Test that done verification steps don't trigger reminder.

        Given: Verification step with status=done
        When: check_verification_reminder is called
        Then: No reminder should be returned
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "done_final_certification": create_step(
                "done_final_certification",
                kind="verification",
                status="done"
            ),
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True
        assert result.get("reminder") == "" or result.get("reminder") is None


class TestNeverBlocksBehavior:
    """Test that function never blocks (always returns allow=True)."""

    def test_always_returns_allow_true(self):
        """
        Test that function always returns allow=True regardless of steps.

        Given: Any steps configuration
        When: check_verification_reminder is called
        Then: allow should always be True (warn-only mode)
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        test_cases = [
            # Empty steps
            {},
            # Pending verification steps
            {"step1": create_step("step1", kind="verification", status="pending")},
            # Multiple pending verifications
            {
                "audit": create_step("audit", kind="verification", status="pending"),
                "trace": create_step("trace", kind="verification", status="in_progress"),
            },
        ]

        for steps in test_cases:
            result = check_verification_reminder(steps)
            assert result["allow"] is True, f"Should always allow for steps: {steps}"
            assert "allow" in result, "Result should have 'allow' key"

    def test_never_returns_allow_false(self):
        """
        Test that function never blocks execution.

        Given: Even with many pending verification steps
        When: check_verification_reminder is called
        Then: Should never return allow=False
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "audit": create_step("audit", kind="verification", status="pending"),
            "trace": create_step("trace", kind="verification", status="pending"),
            "done": create_step("done", kind="verification", status="pending"),
        }

        result = check_verification_reminder(steps)

        # CRITICAL: This is a warn-only function, never blocks
        assert result["allow"] is True, "Function should never block (warn-only)"
        assert "reminder" in result, "Should have reminder even when allowing"


class TestReminderMessageContent:
    """Test the content and format of reminder messages."""

    def test_reminder_includes_pending_step_names(self):
        """
        Test that reminder message includes names of pending verification steps.

        Given: Multiple pending verification steps
        When: check_verification_reminder is called
        Then: Reminder should mention the pending step names
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "audit_quality_checks": create_step(
                "audit_quality_checks",
                kind="verification",
                status="pending"
            ),
            "trace_manual_verification": create_step(
                "trace_manual_verification",
                kind="verification",
                status="in_progress"
            ),
        }

        result = check_verification_reminder(steps)

        assert result["allow"] is True
        assert "reminder" in result
        reminder = result["reminder"]

        # Should mention the pending steps
        assert "audit_quality_checks" in reminder or "audit" in reminder.lower()
        assert "trace_manual_verification" in reminder or "trace" in reminder.lower()

    def test_optional_verification_steps_recognized(self):
        """
        Test that optional verification steps are recognized.

        Given: Optional steps (audit_quality_checks, trace_manual_verification, done_final_certification)
        When: They are in pending state
        Then: They should appear in reminder message
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        # Test each optional step
        optional_steps = [
            "audit_quality_checks",
            "trace_manual_verification",
            "done_final_certification"
        ]

        for step_name in optional_steps:
            steps = {
                step_name: create_step(step_name, kind="verification", status="pending")
            }

            result = check_verification_reminder(steps)

            assert result["allow"] is True
            assert "reminder" in result
            assert step_name in result["reminder"] or step_name.replace("_", " ") in result["reminder"]


class TestMissingStepsDictHandling:
    """Test graceful handling of missing or malformed steps dict."""

    def test_handles_none_steps_gracefully(self):
        """
        Test that None steps parameter is handled gracefully.

        Given: steps parameter is None
        When: check_verification_reminder is called
        Then: Should return default response (allow=True, no reminder)
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        result = check_verification_reminder(None)

        assert result["allow"] is True
        assert result.get("reminder") == "" or result.get("reminder") is None

    def test_handles_empty_dict(self):
        """
        Test that empty steps dict is handled gracefully.

        Given: steps parameter is empty dict {}
        When: check_verification_reminder is called
        Then: Should return allow=True with no reminder
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        result = check_verification_reminder({})

        assert result["allow"] is True
        assert result.get("reminder") == "" or result.get("reminder") is None

    def test_handles_missing_step_fields(self):
        """
        Test that steps with missing fields are handled gracefully.

        Given: Step dict missing 'kind' or 'status' fields
        When: check_verification_reminder is called
        Then: Should not crash, should return valid response
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "malformed_step": {
                "step_id": "bad_step"
                # Missing 'kind' and 'status' fields
            }
        }

        # Should not raise exception
        result = check_verification_reminder(steps)

        assert result["allow"] is True
        # Should handle gracefully
        assert isinstance(result, dict)

    def test_handles_non_dict_steps(self):
        """
        Test that non-dict steps parameter is handled gracefully.

        Given: steps parameter is not a dict (e.g., list, string)
        When: check_verification_reminder is called
        Then: Should return default response without crashing
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        # Test with list
        result = check_verification_reminder([])
        assert result["allow"] is True

        # Test with string
        result = check_verification_reminder("invalid")
        assert result["allow"] is True


class TestReturnFormat:
    """Test that function returns correct format."""

    def test_returns_dict_with_allow_key(self):
        """
        Test that return value is a dict with 'allow' key.

        Given: Any input
        When: check_verification_reminder is called
        Then: Should return dict with 'allow' key
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        result = check_verification_reminder({})

        assert isinstance(result, dict), "Should return dict"
        assert "allow" in result, "Should have 'allow' key"
        assert isinstance(result["allow"], bool), "'allow' should be boolean"

    def test_returns_dict_with_reminder_key(self):
        """
        Test that return value has 'reminder' key.

        Given: Any input
        When: check_verification_reminder is called
        Then: Should return dict with 'reminder' key (string or None)
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        result = check_verification_reminder({})

        assert "reminder" in result, "Should have 'reminder' key"
        # Reminder should be string or None
        assert result["reminder"] is None or isinstance(result["reminder"], str)

    def test_reminder_is_string_when_present(self):
        """
        Test that reminder value is a non-empty string when present.

        Given: Pending verification steps exist
        When: check_verification_reminder is called
        Then: Reminder should be a non-empty string
        """
        from StopHook_skill_execution_gate import check_verification_reminder

        steps = {
            "audit": create_step("audit", kind="verification", status="pending")
        }

        result = check_verification_reminder(steps)

        if result.get("reminder"):
            assert isinstance(result["reminder"], str)
            assert len(result["reminder"]) > 0
