"""Tests for migration status classification in _skill_frontmatter_loader."""

from __future__ import annotations

import pytest

from skill_guard._skill_frontmatter_loader import classify_migration_status, build_migration_result


class TestClassifyMigrationStatus:
    """UNMIGRATED cases — no contract-era contract_type or completion fields."""

    def test_no_contract_type_advisory_enforcement(self):
        fm = {"enforcement": "advisory", "description": "A legacy skill"}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_no_contract_type_prose_only(self):
        fm = {"description": "A legacy skill", "version": "1.0.0"}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_legacy_workflow_type_no_contract_fields(self):
        # "workflow" is the legacy type from _VALID_CONTRACT_TYPES;
        # it is not a contract-era type (workflow-execution is).
        fm = {"contract_type": "workflow", "workflow_steps": ["step one"]}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_legacy_output_type_no_contract_fields(self):
        fm = {"contract_type": "output", "required_sections": ["analysis"]}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_legacy_analysis_type(self):
        fm = {"contract_type": "analysis", "category": "knowledge"}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_missing_all_contract_era_fields(self):
        fm = {"contract_type": "workflow", "enforcement": "strict", "workflow_steps": ["a"]}
        assert classify_migration_status(fm) == "UNMIGRATED"

    def test_unmigrated_when_only_allowed_tools_now_present(self):
        # allowed_tools_now without contract_type or core completion field
        fm = {"allowed_tools_now": ["Bash"], "enforcement": "strict"}
        assert classify_migration_status(fm) == "UNMIGRATED"


class TestClassifyMigrationStatusPartiallyMigrated:
    """PARTIALLY_MIGRATED cases — contract_type present but core field missing."""

    def test_workflow_execution_missing_required_artifacts(self):
        fm = {"contract_type": "workflow-execution", "allowed_tools_now": ["Bash"]}
        assert classify_migration_status(fm) == "PARTIALLY_MIGRATED"

    def test_workflow_execution_empty_required_artifacts(self):
        fm = {"contract_type": "workflow-execution", "required_artifacts": []}
        assert classify_migration_status(fm) == "MIGRATED"

    def test_structured_output_missing_response_requirements(self):
        fm = {"contract_type": "structured-output", "allowed_tools_now": ["Read"]}
        assert classify_migration_status(fm) == "PARTIALLY_MIGRATED"

    def test_structured_output_empty_response_requirements(self):
        fm = {"contract_type": "structured-output", "response_requirements": {}}
        assert classify_migration_status(fm) == "MIGRATED"

    def test_hybrid_missing_required_artifacts(self):
        fm = {"contract_type": "hybrid", "response_requirements": {"sections": ["x"]}}
        assert classify_migration_status(fm) == "PARTIALLY_MIGRATED"

    def test_hybrid_missing_response_requirements(self):
        fm = {"contract_type": "hybrid", "required_artifacts": ["foo.json"]}
        assert classify_migration_status(fm) == "PARTIALLY_MIGRATED"

    def test_has_completion_field_but_no_contract_type(self):
        # Edge: has required_artifacts but no contract_type — partial
        fm = {"required_artifacts": ["artifact.json"], "enforcement": "strict"}
        assert classify_migration_status(fm) == "PARTIALLY_MIGRATED"


class TestClassifyMigrationStatusMigrated:
    """MIGRATED cases — contract_type present and core field(s) present."""

    def test_workflow_execution_complete(self):
        fm = {
            "contract_type": "workflow-execution",
            "required_artifacts": ["output.json"],
            "allowed_tools_now": ["Bash", "Read"],
        }
        assert classify_migration_status(fm) == "MIGRATED"

    def test_workflow_execution_multiple_artifacts(self):
        fm = {
            "contract_type": "workflow-execution",
            "required_artifacts": ["a.json", "b.json"],
        }
        assert classify_migration_status(fm) == "MIGRATED"

    def test_structured_output_complete(self):
        fm = {
            "contract_type": "structured-output",
            "response_requirements": {"sections": ["analysis", "summary"]},
        }
        assert classify_migration_status(fm) == "MIGRATED"

    def test_hybrid_complete(self):
        fm = {
            "contract_type": "hybrid",
            "required_artifacts": ["artifact.json"],
            "response_requirements": {"sections": ["x"]},
        }
        assert classify_migration_status(fm) == "MIGRATED"


class TestBuildMigrationResult:
    """build_migration_result returns the correct action for each status."""

    def test_migrated_action_none(self):
        fm = {
            "contract_type": "workflow-execution",
            "required_artifacts": ["out.json"],
        }
        result = build_migration_result("test-skill", fm)
        assert result["skill"] == "test-skill"
        assert result["status"] == "MIGRATED"
        assert result["action"] == "none"
        assert "no migration needed" in result["reason"]
        assert result["missing_fields"] == []
        assert result["validation_warnings"] == []

    def test_partially_migrated_action_plan(self):
        fm = {"contract_type": "workflow-execution"}
        result = build_migration_result("my-skill", fm)
        assert result["skill"] == "my-skill"
        assert result["status"] == "PARTIALLY_MIGRATED"
        assert result["action"] == "plan"
        assert "required_artifacts" in result["missing_fields"]

    def test_unmigrated_action_plan(self):
        fm = {"enforcement": "advisory"}
        result = build_migration_result("legacy-skill", fm)
        assert result["skill"] == "legacy-skill"
        assert result["status"] == "UNMIGRATED"
        assert result["action"] == "plan"
        assert "legacy" in result["reason"]

    def test_partially_migrated_includes_validation_warnings(self):
        fm = {"contract_type": "structured-output"}
        result = build_migration_result("my-skill", fm, validation_warnings=["Missing name"])
        assert result["validation_warnings"] == ["Missing name"]
        # PARTIALLY_MIGRATED reports the core gap (response_requirements) plus
        # allowed_tools_now as supporting metadata
        assert result["missing_fields"] == ["response_requirements"]


class TestClassifyMigrationStatusWithWarnings:
    """Validation warnings are accepted but do not override presence of core fields."""

    def test_complete_workflow_with_warnings_still_migrated(self):
        fm = {
            "contract_type": "workflow-execution",
            "required_artifacts": ["out.json"],
        }
        warnings = ["Missing version field"]
        assert classify_migration_status(fm, warnings) == "MIGRATED"

    def test_incomplete_workflow_with_warnings_remains_partially(self):
        fm = {"contract_type": "workflow-execution", "allowed_tools_now": ["Bash"]}
        warnings = ["Missing required_artifacts"]
        assert classify_migration_status(fm, warnings) == "PARTIALLY_MIGRATED"


class TestClassifyMigrationStatusResultValues:
    """Sanity: classify_migration_status always returns one of the three values."""

    @pytest.mark.parametrize("fm", [
        {"contract_type": "workflow-execution", "required_artifacts": ["a.json"]},
        {"contract_type": "structured-output", "response_requirements": {"sections": []}},
        {"contract_type": "hybrid", "required_artifacts": [], "response_requirements": {}},
        {"enforcement": "advisory"},
        {"contract_type": "workflow"},
        {},
    ])
    def test_result_is_one_of_three(self, fm):
        result = classify_migration_status(fm)
        assert result in {"UNMIGRATED", "PARTIALLY_MIGRATED", "MIGRATED"}


class TestClassifyMigrationStatusRobustness:
    """None / malformed frontmatter must not raise."""

    def test_none_frontmatter_returns_unmigrated(self):
        assert classify_migration_status(None) == "UNMIGRATED"

    def test_none_with_warnings_returns_unmigrated(self):
        assert classify_migration_status(None, ["Missing version"]) == "UNMIGRATED"

    def test_empty_dict_returns_unmigrated(self):
        assert classify_migration_status({}) == "UNMIGRATED"

    def test_empty_dict_with_warnings_returns_unmigrated(self):
        assert classify_migration_status({}, ["Missing name"]) == "UNMIGRATED"

    def test_build_migration_result_none_returns_unmigrated_plan(self):
        result = build_migration_result("missing-skill", None)
        assert result["status"] == "UNMIGRATED"
        assert result["action"] == "plan"
        assert result["missing_fields"] == ["*"]

    def test_build_migration_result_empty_returns_unmigrated_plan(self):
        result = build_migration_result("empty-skill", {})
        assert result["status"] == "UNMIGRATED"
        assert result["action"] == "plan"

    def test_has_contract_field_none_returns_false(self):
        from skill_guard._skill_frontmatter_loader import _has_contract_field
        assert _has_contract_field(None, "required_artifacts") is False

    def test_is_contract_era_none_returns_false(self):
        from skill_guard._skill_frontmatter_loader import is_contract_era
        assert is_contract_era(None) is False