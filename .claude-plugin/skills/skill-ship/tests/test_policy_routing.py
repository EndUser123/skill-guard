"""Tests for policy routing in skill-ship."""

import json
import sys
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_policy():
    policy_path = Path(__file__).parent.parent / "config" / "policy.json"
    return json.loads(policy_path.read_text())


class TestPolicyRouting:
    """Test suite for Phase 1.7 policy routing."""

    def test_prompt_skill_routes_to_3a_3b(self):
        """prompt_skill artifact type routes to minimal phases."""
        policy = load_policy()
        entry = policy["artifact_types"]["prompt_skill"]
        assert entry["phases"] == ["3a", "3b"]
        assert entry["risk_level"] == "low"

    def test_new_skill_routes_to_3e_3f(self):
        """new_skill routes through evaluator and judge."""
        policy = load_policy()
        entry = policy["artifact_types"]["new_skill"]
        assert "3e" in entry["phases"]
        assert "3f" in entry["phases"]

    def test_orchestrator_routes_to_all_phases(self):
        """orchestrator routes to full pipeline including 3d."""
        policy = load_policy()
        entry = policy["artifact_types"]["orchestrator"]
        assert "3a" in entry["phases"]
        assert "3b" in entry["phases"]
        assert "3c" in entry["phases"]
        assert "3d" in entry["phases"]
        assert "3e" in entry["phases"]
        assert "3f" in entry["phases"]
        assert entry["risk_level"] == "high"

    def test_contract_change_routes_to_high_risk(self):
        """contract_change routes to high risk category."""
        policy = load_policy()
        entry = policy["artifact_types"]["contract_change"]
        assert entry["risk_level"] == "high"
        assert "3e" in entry["phases"]
        assert "3f" in entry["phases"]

    def test_distribution_update_routes_to_3a_3b_3c(self):
        """distribution_update skips 3d, 3e, 3f — only structural and safety checks."""
        policy = load_policy()
        entry = policy["artifact_types"]["distribution_update"]
        assert "3a" in entry["phases"]
        assert "3b" in entry["phases"]
        assert "3c" in entry["phases"]
        assert "3d" not in entry["phases"]
        assert "3e" not in entry["phases"]
        assert "3f" not in entry["phases"]

    def test_default_includes_3e_3f(self):
        """Unknown artifact types use default which includes evaluator/judge."""
        policy = load_policy()
        default = policy["default"]
        assert "3e" in default["phases"]
        assert "3f" in default["phases"]
        assert default["risk_level"] == "medium"

    def test_all_artifact_types_have_risk_level(self):
        """Every artifact type has a risk_level field."""
        policy = load_policy()
        for name, entry in policy["artifact_types"].items():
            assert "risk_level" in entry, f"{name} missing risk_level"
            assert entry["risk_level"] in ("low", "medium", "high")

    def test_default_has_phases_and_risk_level(self):
        """Default entry has both phases and risk_level."""
        policy = load_policy()
        default = policy["default"]
        assert "phases" in default
        assert "risk_level" in default
        assert isinstance(default["phases"], list)
        assert len(default["phases"]) > 0

    def test_policy_json_is_valid(self):
        """Policy file is valid JSON with required structure."""
        policy = load_policy()
        assert "artifact_types" in policy
        assert "default" in policy
        assert len(policy["artifact_types"]) == 5
        expected_types = {"prompt_skill", "new_skill", "orchestrator", "contract_change", "distribution_update"}
        assert set(policy["artifact_types"].keys()) == expected_types

    def test_else_branch_unknown_type(self):
        """When artifact type not in policy, default is used (no crash)."""
        policy = load_policy()
        unknown_type = "unknown_type_xyz"
        matched = policy["artifact_types"].get(unknown_type)
        assert matched is None  # Not found
        # Fallback to default
        result = policy["default"]
        assert "phases" in result
        assert "risk_level" in result

    def test_prompt_skill_bypasses_3e_3f(self):
        """prompt_skill has bypass_3e_3f=true - evaluator/judge skipped for low-risk changes."""
        policy = load_policy()
        entry = policy["artifact_types"]["prompt_skill"]
        assert entry.get("bypass_3e_3f") is True
        assert "bypass_reason" in entry
        assert len(entry["bypass_reason"]) > 0
        # Phases list should not include 3e or 3f
        assert "3e" not in entry["phases"]
        assert "3f" not in entry["phases"]

    def test_distribution_update_bypasses_3e_3f(self):
        """distribution_update has bypass_3e_3f=true - evaluator/judge skipped for metadata-only changes."""
        policy = load_policy()
        entry = policy["artifact_types"]["distribution_update"]
        assert entry.get("bypass_3e_3f") is True
        assert "bypass_reason" in entry
        # Phases list should not include 3e or 3f
        assert "3e" not in entry["phases"]
        assert "3f" not in entry["phases"]

    def test_new_skill_does_not_bypass_3e_3f(self):
        """new_skill does NOT bypass evaluator/judge - full pipeline required."""
        policy = load_policy()
        entry = policy["artifact_types"]["new_skill"]
        assert entry.get("bypass_3e_3f") is not True
        assert "3e" in entry["phases"]
        assert "3f" in entry["phases"]

    def test_orchestrator_does_not_bypass_3e_3f(self):
        """orchestrator does NOT bypass evaluator/judge - high risk requires full pipeline."""
        policy = load_policy()
        entry = policy["artifact_types"]["orchestrator"]
        assert entry.get("bypass_3e_3f") is not True
        assert "3e" in entry["phases"]
        assert "3f" in entry["phases"]

    def test_bypass_flag_only_on_low_risk_types(self):
        """Only low/medium risk artifact types should have bypass_3e_3f=true."""
        policy = load_policy()
        for name, entry in policy["artifact_types"].items():
            if entry.get("bypass_3e_3f") is True:
                assert entry["risk_level"] in ("low", "medium"), f"{name} has bypass_3e_3f but risk_level={entry['risk_level']}"

    def test_bypass_reason_is_descriptive(self):
        """bypass_reason should explain WHY evaluation is skipped."""
        policy = load_policy()
        for name, entry in policy["artifact_types"].items():
            if entry.get("bypass_3e_3f") is True:
                reason = entry["bypass_reason"]
                assert len(reason) > 10, f"{name} bypass_reason too short: {reason}"
                assert not reason.endswith("."), f"{name} bypass_reason should not end with period"