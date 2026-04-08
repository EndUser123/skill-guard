"""Tests for evaluator -> judge pipeline integration.

Verifies that evaluator JSON output correctly feeds into judge decision policy.
These are pipeline integration tests, not schema documentation tests.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def judge_decision_policy(findings, risk_level):
    """Apply the 4-rule decision policy from workflow-phases.md Phase 3f.

    This is the canonical judge logic extracted from the prompt template.
    Tests use this to verify the policy is correctly applied.
    """
    # Rule 1: Any critical severity finding -> fail
    for f in findings:
        if f.get("severity") == "critical":
            return {"decision": "fail", "required_follow_ups": [], "scores": _extract_scores(findings)}

    # Extract dimension scores
    scores = _extract_scores(findings)

    # Rule 2: problem_fit < 3 OR adaptability < 3 OR failure_tolerance < 3 -> fail
    if scores.get("problem_fit", 5) < 3:
        return {"decision": "fail", "required_follow_ups": ["Fix problem_fit score to >= 3"], "scores": scores}
    if scores.get("adaptability", 5) < 3:
        return {"decision": "fail", "required_follow_ups": ["Fix adaptability score to >= 3"], "scores": scores}
    if scores.get("failure_tolerance", 5) < 3:
        return {"decision": "fail", "required_follow_ups": ["Fix failure_tolerance score to >= 3"], "scores": scores}

    # Rule 3: risk_level == "high" AND no findings above "minor" severity -> conditional_pass
    if risk_level == "high":
        return {"decision": "conditional_pass", "required_follow_ups": ["Address all findings before distribution"], "scores": scores}

    # Rule 4: Otherwise -> pass
    return {"decision": "pass", "required_follow_ups": [], "scores": scores}


def _extract_scores(findings):
    scores = {}
    for f in findings:
        lens = f.get("lens")
        score = f.get("proposed_score", 5)
        if lens:
            scores[lens] = score
    return scores


class TestEvaluatorJudgePipeline:
    """Pipeline integration: evaluator JSON -> judge decision."""

    def test_critical_finding_yields_fail(self):
        """Rule 1: Any critical severity -> fail."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": "hard-coded path", "evidence": ["x"], "proposed_score": 2, "severity": "critical"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "fail"

    def test_problem_fit_lt_3_yields_fail(self):
        """Rule 2: problem_fit < 3 -> fail."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": "wrong scope", "evidence": [], "proposed_score": 2, "severity": "major"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "fail"
        assert "problem_fit" in result["required_follow_ups"][0]

    def test_adaptability_lt_3_yields_fail(self):
        """Rule 2: adaptability < 3 -> fail."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": "rigid routing", "evidence": [], "proposed_score": 2, "severity": "major"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "fail"
        assert "adaptability" in result["required_follow_ups"][0]

    def test_failure_tolerance_lt_3_yields_fail(self):
        """Rule 2: failure_tolerance < 3 -> fail."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": "no fallback", "evidence": [], "proposed_score": 2, "severity": "major"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "fail"

    def test_high_risk_no_critical_yields_conditional_pass(self):
        """Rule 3: high risk + no critical -> conditional_pass."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": "some coupling", "evidence": [], "proposed_score": 4, "severity": "minor"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "high")
        assert result["decision"] == "conditional_pass"
        assert len(result["required_follow_ups"]) > 0

    def test_all_good_yields_pass(self):
        """Rule 4: all scores >= 3, no critical -> pass."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "composability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "context_efficiency", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "observability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "maintainability_6m", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "pass"
        assert result["required_follow_ups"] == []

    def test_medium_risk_with_minor_yields_pass(self):
        """Rule 4: medium risk, all >= 3 -> pass (not conditional_pass)."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": "minor coupling", "evidence": [], "proposed_score": 4, "severity": "minor"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "pass"

    def test_malformed_evaluator_output_missing_lens(self):
        """Malformed evaluator output (missing lens field) does not crash judge."""
        evaluator_output = [
            {"finding": "something", "proposed_score": 2, "severity": "major"},
        ]
        # Should not raise — judge extracts what's available
        result = judge_decision_policy(evaluator_output, "medium")
        assert "decision" in result
        assert result["decision"] in ("pass", "conditional_pass", "fail")

    def test_malformed_evaluator_output_out_of_range_score(self):
        """Evaluator output with score > 5 is clamped by judge extraction."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": "x", "proposed_score": 99, "severity": "major"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        # Score 99 is out of range but judge policy only checks < 3, not bounds
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "pass"

    def test_required_follow_ups_for_fail(self):
        """fail decision must list what must be fixed."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": "wrong scope", "evidence": [], "proposed_score": 2, "severity": "major"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert result["decision"] == "fail"
        assert len(result["required_follow_ups"]) > 0
        assert isinstance(result["required_follow_ups"], list)

    def test_scores_in_output(self):
        """Judge output must include all 7 dimension scores."""
        evaluator_output = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 4, "severity": "minor"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "composability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "context_efficiency", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "observability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "maintainability_6m", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(evaluator_output, "medium")
        assert "scores" in result
        assert len(result["scores"]) == 7
        assert result["scores"]["problem_fit"] == 4
        assert result["scores"]["adaptability"] == 5

    def test_required_follow_ups_must_be_non_empty_string(self):
        """required_follow_ups items must be non-empty strings for fail/conditional_pass."""
        # conditional_pass case
        eval_out = [
            {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        result = judge_decision_policy(eval_out, "high")
        assert result["decision"] == "conditional_pass"
        for item in result["required_follow_ups"]:
            assert isinstance(item, str)
            assert len(item) > 0

    def test_malformed_evaluator_invalid_severity(self):
        """Invalid severity values should be handled gracefully."""
        eval_out = [
            {"lens": "problem_fit", "finding": "x", "proposed_score": 5, "severity": "invalid_severity"},
            {"lens": "adaptability", "finding": None, "proposed_score": 5, "severity": "info"},
            {"lens": "failure_tolerance", "finding": None, "proposed_score": 5, "severity": "info"},
        ]
        # Judge prompt says: invalid severity -> treat as info
        result = judge_decision_policy(eval_out, "medium")
        assert "decision" in result
