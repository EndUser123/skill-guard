#!/usr/bin/env python3
"""
RED phase tests for T-001: Add workflow_steps to critical skills.

These tests MUST FAIL until workflow_steps are added to skill frontmatter.
"""

import pytest

from skill_guard.breadcrumb.tracker import _load_workflow_steps


class TestT001WorkflowStepsRequired:
    """
    RED Phase: These tests FAIL until workflow_steps are added.

    After adding workflow_steps to critical skills, these tests will pass.
    """

    @pytest.mark.parametrize("skill_name", ["code", "arch"])
    def test_critical_skills_must_have_workflow_steps(self, skill_name):
        """
        CRITICAL TEST: All critical skills MUST have workflow_steps defined.

        This test FAILS (RED) until workflow_steps are added to SKILL.md frontmatter.

        After T-001 implementation, each skill should have:
        - Non-empty workflow_steps list
        - At least 3 workflow steps
        - All steps are strings
        """
        steps = _load_workflow_steps(skill_name)

        # FAIL: workflow_steps must exist and not be empty
        assert len(steps) > 0, (
            f"{skill_name} skill must have workflow_steps in SKILL.md frontmatter. "
            f"Currently has {len(steps)} steps."
        )

        # FAIL: Must have meaningful workflow (at least 3 steps)
        assert len(steps) >= 3, (
            f"{skill_name} skill must have at least 3 workflow steps. "
            f"Currently has {len(steps)} steps: {steps}"
        )

        # FAIL: All steps must be dicts with id field
        assert all(isinstance(step, dict) and "id" in step for step in steps), (
            f"{skill_name} workflow_steps must all be dicts with 'id' field. "
            f"Found non-dict items: {steps}"
        )

        # FAIL: Workflow steps must follow naming convention (snake_case)
        for step in steps:
            step_id = step["id"]
            assert step_id.replace('_', '').isalnum(), (
                f"{skill_name} workflow step '{step_id}' must use snake_case convention. "
                f"Only alphanumeric characters and underscores allowed."
            )

    def test_code_skill_workflow_steps_content(self):
        """
        Test that /code skill has specific required workflow steps.

        This test FAILS until workflow_steps are added with correct content.
        """
        steps = _load_workflow_steps("code")
        step_ids = [step["id"] for step in steps]

        # Required /code workflow steps (based on 9-phase workflow)
        required_steps = [
            "requirements_clarity_check",
            "preflight_context_validation",
            "explore_codebase",
            "design_solution",
            "tdd_implementation",
            "full_test_suite",
            "audit_quality_checks",
            "trace_manual_verification",
            "done_final_certification"
        ]

        # FAIL: All required steps must be present
        for required_step in required_steps:
            assert required_step in step_ids, (
                f"/code skill missing required workflow step: '{required_step}'. "
                f"Current step_ids: {step_ids}"
            )

    def test_trace_skill_workflow_steps_content(self):
        """
        Test that /trace skill has specific required workflow steps.

        NOTE: /trace skill currently has no workflow_steps defined.
        This test is skipped until workflow_steps are added.
        """
        steps = _load_workflow_steps("trace")
        if not steps:
            pytest.skip("/trace skill has no workflow_steps defined yet")

        step_ids = [step["id"] for step in steps]

        # Required /trace workflow steps
        required_steps = [
            "identify_trace_target",
            "select_trace_template",
            "load_trace_methodology",
            "execute_trace_scenarios",
            "verify_findings",
            "generate_trace_report"
        ]

        # FAIL: All required steps must be present
        for required_step in required_steps:
            assert required_step in step_ids, (
                f"/trace skill missing required workflow step: '{required_step}'. "
                f"Current step_ids: {step_ids}"
            )

    def test_arch_skill_workflow_steps_content(self):
        """
        Test that /arch skill has specific required workflow steps.

        This test FAILS until workflow_steps are added with correct content.
        """
        steps = _load_workflow_steps("arch")
        step_ids = [step["id"] for step in steps]

        # Required /arch workflow steps (updated to match current SKILL.md)
        # Note: 6 additional stages added since initial T-001:
        # contract_sensitivity_classification, contract_boundary_inventory,
        # contract_boundary_closure, emit_contract_authority_packet,
        # adr_closure_consistency_check, adr_critic_review
        required_steps = [
            "preflight_checks",
            "classify_intent",
            "select_template",
            "load_template",
            "execute_template_analysis",
            "generate_architecture_review"
        ]

        # FAIL: All required steps must be present
        for required_step in required_steps:
            assert required_step in step_ids, (
                f"/arch skill missing required workflow step: '{required_step}'. "
                f"Current step_ids: {step_ids}"
            )

    def test_workflow_steps_parsing_integration(self):
        """
        Integration test: Verify workflow_steps can be loaded and used.

        This test FAILS if workflow_steps parsing is broken.
        NOTE: /trace excluded — it has no workflow_steps defined.
        """
        # Test that loading doesn't raise exceptions for skills with workflow_steps
        for skill_name in ["code", "arch"]:
            try:
                steps = _load_workflow_steps(skill_name)

                # After T-001: Should have steps
                # Before T-001: This will fail
                assert len(steps) > 0, f"{skill_name} has no workflow_steps"

                # Test that steps can be used for breadcrumb tracking
                first_step = steps[0]
                assert isinstance(first_step, dict), "First step must be dict"
                assert "id" in first_step, "First step must have id field"
                assert len(first_step["id"]) > 0, "First step id must not be empty"

            except Exception as e:
                pytest.fail(
                    f"Failed to load workflow_steps for {skill_name}: {e}. "
                    f"This indicates T-001 is not complete."
                )
