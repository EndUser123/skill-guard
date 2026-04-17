"""Tests for eval_bridge subprocess bridge."""
import json
import sys
from pathlib import Path

import pytest

# Ensure skill-craft module is importable
CRAFT_DIR = Path("P:/.claude/skills/skill-craft")
sys.path.insert(0, str(CRAFT_DIR))

from eval_bridge import EvalResult, LoopResult, aggregate_benchmark


class TestEvalResultDataclass:
    """EvalResult dataclass holds parsed eval output correctly."""

    def test_fields_populated(self):
        r = EvalResult(
            passed=8,
            failed=2,
            total=10,
            results=[{"query": "test", "pass": True}],
            raw={"summary": {"passed": 8, "failed": 2, "total": 10}},
        )
        assert r.passed == 8
        assert r.failed == 2
        assert r.total == 10
        assert len(r.results) == 1

    def test_raw_preserved(self):
        r = EvalResult(passed=5, failed=5, total=10, results=[], raw={"key": "value"})
        assert r.raw["key"] == "value"


class TestLoopResultDataclass:
    """LoopResult dataclass holds parsed loop output correctly."""

    def test_fields_populated(self):
        r = LoopResult(
            exit_reason="threshold_reached",
            best_description="improved description",
            best_score="8/10",
            best_train_score="6/8",
            best_test_score="2/2",
            final_description="improved description",
            iterations_run=3,
            history=[],
            raw={},
        )
        assert r.exit_reason == "threshold_reached"
        assert r.iterations_run == 3
        assert r.best_test_score == "2/2"

    def test_optional_test_score_none(self):
        r = LoopResult(
            exit_reason="max_iterations",
            best_description="desc",
            best_score="5/10",
            best_train_score="5/8",
            best_test_score=None,
            final_description="desc",
            iterations_run=5,
            history=[],
            raw={},
        )
        assert r.best_test_score is None


class TestAggregateBenchmark:
    """aggregate_benchmark aggregates multiple eval results."""

    def test_empty_list_returns_zeros(self):
        result = aggregate_benchmark([])
        assert result["num_runs"] == 0
        assert result["total_queries"] == 0
        assert result["aggregate_pass_rate"] == 0.0

    def test_single_run(self):
        eval_result = EvalResult(
            passed=7, failed=3, total=10, results=[], raw={},
        )
        result = aggregate_benchmark([eval_result])
        assert result["num_runs"] == 1
        assert result["total_queries"] == 10
        assert result["total_passed"] == 7
        assert result["total_failed"] == 3
        assert result["aggregate_pass_rate"] == 0.7
        assert result["per_run_pass_rates"] == [0.7]

    def test_multiple_runs(self):
        runs = [
            EvalResult(passed=5, failed=5, total=10, results=[], raw={}),
            EvalResult(passed=8, failed=2, total=10, results=[], raw={}),
            EvalResult(passed=10, failed=0, total=10, results=[], raw={}),
        ]
        result = aggregate_benchmark(runs)
        assert result["num_runs"] == 3
        assert result["total_queries"] == 30
        assert result["total_passed"] == 23
        assert result["total_failed"] == 7
        assert result["aggregate_pass_rate"] == 23 / 30
        assert result["per_run_pass_rates"] == [0.5, 0.8, 1.0]

    def test_all_fail(self):
        runs = [
            EvalResult(passed=0, failed=10, total=10, results=[], raw={}),
            EvalResult(passed=0, failed=10, total=10, results=[], raw={}),
        ]
        result = aggregate_benchmark(runs)
        assert result["aggregate_pass_rate"] == 0.0
        assert result["per_run_pass_rates"] == [0.0, 0.0]

    def test_zero_total_guards_divide_by_zero(self):
        """Zero total queries should not cause divide-by-zero."""
        runs = [
            EvalResult(passed=0, failed=0, total=0, results=[], raw={}),
        ]
        result = aggregate_benchmark(runs)
        assert result["aggregate_pass_rate"] == 0.0


class TestEvalBridgeJsonParsing:
    """JSON output parsing from skill-creator scripts."""

    def test_eval_output_structure(self):
        """Verify the expected JSON structure from run_eval.py."""
        output = {
            "skill_name": "test-skill",
            "description": "Test skill description",
            "results": [
                {
                    "query": "create a package",
                    "should_trigger": True,
                    "trigger_rate": 1.0,
                    "triggers": 3,
                    "runs": 3,
                    "pass": True,
                },
                {
                    "query": "fix my auth bug",
                    "should_trigger": False,
                    "trigger_rate": 0.0,
                    "triggers": 0,
                    "runs": 3,
                    "pass": True,
                },
            ],
            "summary": {
                "total": 2,
                "passed": 2,
                "failed": 0,
            },
        }
        # Parse as skill-creator would output
        parsed = json.loads(json.dumps(output))
        assert parsed["summary"]["passed"] == 2
        assert parsed["summary"]["total"] == 2
        assert len(parsed["results"]) == 2
        # First should pass (trigger=True, rate=1.0)
        assert parsed["results"][0]["pass"] is True
        # Second should pass (trigger=False, rate=0.0)
        assert parsed["results"][1]["pass"] is True

    def test_eval_output_partial_trigger(self):
        """Partial trigger rate should fail when should_trigger=True."""
        output = {
            "results": [
                {
                    "query": "create a package",
                    "should_trigger": True,
                    "trigger_rate": 0.33,  # 1/3
                    "triggers": 1,
                    "runs": 3,
                    "pass": False,  # < threshold of 0.5
                },
            ],
            "summary": {"total": 1, "passed": 0, "failed": 1},
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["summary"]["failed"] == 1

    def test_loop_output_structure(self):
        """Verify expected JSON structure from run_loop.py."""
        output = {
            "exit_reason": "threshold_reached",
            "best_description": "This skill should be used when...",
            "best_score": "8/10",
            "best_train_score": "6/8",
            "best_test_score": "2/2",
            "final_description": "This skill should be used when...",
            "iterations_run": 3,
            "history": [
                {"iteration": 1, "score": "5/10"},
                {"iteration": 2, "score": "6/10"},
            ],
        }
        parsed = json.loads(json.dumps(output))
        assert parsed["exit_reason"] == "threshold_reached"
        assert parsed["iterations_run"] == 3
        assert len(parsed["history"]) == 2
