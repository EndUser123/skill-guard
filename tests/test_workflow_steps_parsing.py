#!/usr/bin/env python3
"""
Test workflow_steps parsing from SKILL.md frontmatter.

Tests that verify _load_workflow_steps() can extract workflow_steps
from skill frontmatter for breadcrumb tracking.
"""

from pathlib import Path

from skill_guard.breadcrumb.tracker import _load_workflow_steps


class TestWorkflowStepsParsing:
    """Test workflow_steps extraction from SKILL.md frontmatter."""

    def test_load_workflow_steps_from_code_skill(self):
        """Test loading workflow_steps from /code skill SKILL.md."""
        steps = _load_workflow_steps("code")
        assert isinstance(steps, list)

        if steps:
            # Validate structure (dict format with id field)
            assert all(isinstance(step, dict) and "id" in step for step in steps)
            # Match current /code SKILL.md workflow_steps
            # (consumer_contract_precheck, producer_consumer_trace_verification added;
            #  verification steps migrated to dict format)
            expected_step_ids = [
                "pre_execution_checklist",
                "analyze_query_intent",
                "select_execution_model",
                "resolve_plan_state",
                "initialize_resume_ledger",
                "requirements_clarity_check",
                "preflight_context_validation",
                "explore_codebase",
                "design_solution",
                "consumer_contract_precheck",
                "tdd_implementation",
                "smoke_validation",
                "full_test_suite",
                "tier0_checklist_verification",
                "audit_quality_checks",
                "critique_agent_review",
                "trace_manual_verification",
                "producer_consumer_trace_verification",
                "done_final_certification",
            ]
            actual_ids = [step["id"] for step in steps]
            assert actual_ids == expected_step_ids

    def test_load_workflow_steps_from_trace_skill(self):
        """Test loading workflow_steps from /trace skill SKILL.md."""
        steps = _load_workflow_steps("trace")
        assert isinstance(steps, list)

        if steps:
            # Validate dict format with id field
            assert all(isinstance(step, dict) and "id" in step for step in steps)
            # /trace workflow step IDs
            expected_step_ids = [
                "identify_trace_target",
                "select_trace_template",
                "load_trace_methodology",
                "execute_trace_scenarios",
                "verify_findings",
                "generate_trace_report"
            ]
            actual_ids = [step["id"] for step in steps]
            assert actual_ids == expected_step_ids

    def test_load_workflow_steps_from_arch_skill(self):
        """Test loading workflow_steps from /arch skill SKILL.md."""
        steps = _load_workflow_steps("arch")
        assert isinstance(steps, list)

        if steps:
            # Validate dict format with id field
            assert all(isinstance(step, dict) and "id" in step for step in steps)
            # Match current /arch SKILL.md workflow_steps (6 new stages added since T-001):
            # contract_sensitivity_classification, contract_boundary_inventory,
            # contract_boundary_closure, emit_contract_authority_packet,
            # adr_closure_consistency_check, adr_critic_review
            expected_step_ids = [
                "preflight_checks",
                "classify_intent",
                "contract_sensitivity_classification",
                "select_template",
                "load_template",
                "execute_template_analysis",
                "contract_boundary_inventory",
                "contract_boundary_closure",
                "emit_contract_authority_packet",
                "adr_closure_consistency_check",
                "adr_critic_review",
                "generate_architecture_review",
            ]
            actual_ids = [step["id"] for step in steps]
            assert actual_ids == expected_step_ids

    def test_load_workflow_steps_from_nonexistent_skill(self):
        """Test loading workflow_steps from skill that doesn't exist."""
        steps = _load_workflow_steps("nonexistent_skill")
        assert steps == []  # Should return empty list for missing skill

    def test_load_workflow_steps_from_malformed_frontmatter(self, tmp_path):
        """Test loading workflow_steps from skill with malformed frontmatter."""
        # Create a skill with malformed frontmatter
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "invalid: yaml: content:\n"
            "---\n"
            "# Test Skill\n"
        )

        # This should not raise exception, should return empty list
        steps = _load_workflow_steps("test_skill")
        assert isinstance(steps, list)
