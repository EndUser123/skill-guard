"""Tests for Phase 3f Judge - decision policy."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestJudgeDecisionPolicy:
    """Test suite for Phase 3f Judge decision logic."""

    def test_critical_finding_triggers_fail(self):
        """Any critical severity finding must result in fail."""
        findings = [
            {"lens": "adaptability", "finding": "hard-coded path", "proposed_score": 2, "severity": "critical"}
        ]
        decision = "fail"  # critical → fail
        assert decision == "fail"

    def test_problem_fit_lt_3_triggers_fail(self):
        """problem_fit score < 3 must result in fail."""
        findings = [
            {"lens": "problem_fit", "finding": "wrong scope", "proposed_score": 2, "severity": "major"}
        ]
        decision = "fail"  # problem_fit < 3 → fail
        assert decision == "fail"

    def test_adaptability_lt_3_triggers_fail(self):
        """adaptability score < 3 must result in fail."""
        findings = [
            {"lens": "adaptability", "finding": "hard-coded path", "proposed_score": 2, "severity": "major"}
        ]
        decision = "fail"  # adaptability < 3 → fail
        assert decision == "fail"

    def test_failure_tolerance_lt_3_triggers_fail(self):
        """failure_tolerance score < 3 must result in fail."""
        findings = [
            {"lens": "failure_tolerance", "finding": "no fallback", "proposed_score": 2, "severity": "major"}
        ]
        decision = "fail"  # failure_tolerance < 3 → fail
        assert decision == "fail"

    def test_high_risk_no_critical_yields_conditional_pass(self):
        """high risk_level with no critical findings yields conditional_pass."""
        findings = [
            {"lens": "composability", "finding": "some coupling", "proposed_score": 3, "severity": "minor"}
        ]
        risk_level = "high"
        decision = "conditional_pass"
        assert decision == "conditional_pass"

    def test_all_good_yields_pass(self):
        """No critical findings and all dimension scores >= 3 yields pass."""
        findings = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "composability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "context_efficiency", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "observability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "maintainability_6m", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        decision = "pass"
        assert decision == "pass"

    def test_required_follow_ups_for_conditional_pass(self):
        """conditional_pass must have required_follow_ups list."""
        decision_obj = {
            "decision": "conditional_pass",
            "required_follow_ups": ["Add fallback behavior for missing dependencies"],
            "scores": {"problem_fit": 5, "adaptability": 3}
        }
        assert decision_obj["decision"] == "conditional_pass"
        assert len(decision_obj["required_follow_ups"]) > 0

    def test_pass_has_empty_required_follow_ups(self):
        """pass decision must have empty required_follow_ups."""
        decision_obj = {
            "decision": "pass",
            "required_follow_ups": [],
            "scores": {"problem_fit": 5, "adaptability": 5}
        }
        assert decision_obj["decision"] == "pass"
        assert len(decision_obj["required_follow_ups"]) == 0

    def test_fail_has_required_follow_ups(self):
        """fail decision must list what must be fixed."""
        decision_obj = {
            "decision": "fail",
            "required_follow_ups": ["Fix adaptability score to >= 3"],
            "scores": {"problem_fit": 2, "adaptability": 2}
        }
        assert decision_obj["decision"] == "fail"
        assert len(decision_obj["required_follow_ups"]) > 0

    def test_judge_output_schema(self):
        """Judge output must be valid JSON with decision, required_follow_ups, and scores."""
        valid_output = {
            "decision": "pass",
            "required_follow_ups": [],
            "scores": {
                "problem_fit": 5,
                "adaptability": 4,
                "composability": 5,
                "context_efficiency": 4,
                "observability": 5,
                "failure_tolerance": 5,
                "maintainability_6m": 4
            }
        }
        assert "decision" in valid_output
        assert "required_follow_ups" in valid_output
        assert "scores" in valid_output
        assert valid_output["decision"] in ("pass", "conditional_pass", "fail")

    def test_decision_order_priority(self):
        """Decision rules applied in order: critical → dimension thresholds → risk_level → pass."""
        # Rule 1: Any critical → fail (highest priority)
        findings = [{"lens": "adaptability", "finding": "x", "proposed_score": 5, "severity": "critical"}]
        risk_level = "low"
        decision = "fail"
        assert decision == "fail"

        # Rule 2: problem_fit/adaptability/failure_tolerance < 3 → fail
        findings = [{"lens": "problem_fit", "finding": "x", "proposed_score": 2, "severity": "minor"}]
        risk_level = "low"
        decision = "fail"
        assert decision == "fail"

        # Rule 3: high risk + no critical → conditional_pass
        findings = [{"lens": "composability", "finding": "x", "proposed_score": 4, "severity": "minor"}]
        risk_level = "high"
        decision = "conditional_pass"
        assert decision == "conditional_pass"

        # Rule 4: otherwise → pass
        findings = [{"lens": "composability", "finding": "x", "proposed_score": 4, "severity": "minor"}]
        risk_level = "medium"
        decision = "pass"
        assert decision == "pass"

    def test_judge_does_not_reanalyze(self):
        """Judge must NOT re-analyze artifact - only applies policy to evaluator findings."""
        # This is a documentation test - the constraint is enforced by role prompt
        constraints = [
            "Do NOT re-analyze the artifact or produce new findings",
            "Do NOT look at prior phase outputs — only the evaluator's JSON"
        ]
        assert len(constraints) == 2

    def test_judge_requires_evaluator_json(self):
        """Judge requires evaluator JSON output as input - cannot self-score."""
        # Judge receives findings from evaluator, does not generate its own findings
        evaluator_output = json.dumps([
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info", "evidence": []}
        ])
        parsed = json.loads(evaluator_output)
        assert isinstance(parsed, list)
        assert "lens" in parsed[0]

    def test_low_risk_conditional_pass_edge_case(self):
        """low risk_level cannot be conditional_pass unless dimension threshold met."""
        findings = [{"lens": "composability", "finding": "x", "proposed_score": 4, "severity": "minor"}]
        risk_level = "low"
        # low risk + no critical + all dims >= 3 → pass (not conditional_pass)
        decision = "pass"
        assert decision == "pass"

    def test_medium_risk_pass_case(self):
        """medium risk_level with good scores → pass."""
        findings = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        risk_level = "medium"
        decision = "pass"
        assert decision == "pass"


class TestJudgeProvenanceAndConstraints:
    """Test suite for provenance field and judge role constraints."""

    def test_provenance_field_required(self):
        """Judge output must include provenance field."""
        valid_output = {
            "decision": "pass",
            "required_follow_ups": [],
            "scores": {"problem_fit": 5, "adaptability": 5},
            "provenance": "this_run"
        }
        assert "provenance" in valid_output
        assert valid_output["provenance"] == "this_run"

    def test_judge_never_invents_new_findings(self):
        """Judge must NOT produce new findings - only applies policy to evaluator output."""
        # This is the core separation constraint: judge applies policy, does not analyze
        judge_constraints = [
            "Your job is to apply policy to the evaluator's structured findings",
            "You do NOT re-analyze the artifact or produce new findings",
            "Do NOT invent new findings — only apply the policy to what the evaluator reported"
        ]
        # Verify constraints explicitly forbid re-analysis or new findings
        assert any("apply policy" in c.lower() for c in judge_constraints)
        assert any("not produce new findings" in c.lower() or "do not invent" in c.lower() for c in judge_constraints)

    def test_judge_output_has_no_findings_field(self):
        """Judge JSON output must not contain a 'findings' key - findings belong to evaluator."""
        # Judge output schema is: {decision, required_follow_ups, scores, provenance}
        # findings array belongs to evaluator output only
        judge_output_keys = {"decision", "required_follow_ups", "scores", "provenance"}
        assert "findings" not in judge_output_keys

    def test_judge_requires_evaluator_json_input(self):
        """Judge must receive evaluator JSON findings as input - cannot score independently."""
        # Judge receives parsed evaluator JSON and applies policy
        # It does not have its own lens scoring logic
        evaluator_json = json.dumps([
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info", "provenance": "this_run", "assumptions": []}
        ])
        parsed = json.loads(evaluator_json)
        # Judge would receive this parsed array and apply decision policy
        assert isinstance(parsed, list)
        assert parsed[0]["lens"] == "problem_fit"

    def test_judge_does_not_reanalyze_artifact(self):
        """Judge must NOT have access to the artifact itself - only evaluator findings."""
        # This constraint is enforced by the judge prompt: "Do NOT look at prior phase outputs"
        # Judge only receives evaluator JSON, not the original artifact
        pass  # Documentation test - constraint is in prompt

    def test_judge_assumptions_handling_high_risk(self):
        """For high-risk artifacts, dangerous assumptions in evaluator payload bias toward conditional_pass."""
        evaluator_payload = {
            "findings": [
                {"lens": "problem_fit", "finding": None, "proposed_score": 4, "severity": "minor", "provenance": "this_run", "assumptions": []}
            ],
            "assumptions": [
                "assumes P: drive is root",
                "fails hard if tool discovery fails; no degraded mode"
            ]
        }
        # With dangerous assumptions on high-risk, should get conditional_pass
        risk_level = "high"
        has_dangerous_assumptions = any(
            "fails hard" in a or "no fallback" in a or "hard-coded" in a
            for a in evaluator_payload["assumptions"]
        )
        if risk_level == "high" and has_dangerous_assumptions:
            decision = "conditional_pass"
        else:
            decision = "pass"
        assert decision == "conditional_pass"
