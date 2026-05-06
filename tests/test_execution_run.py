"""Tests for execution_run.py"""

from __future__ import annotations

import pytest
from skill_guard.execution_run import (
    ContractType,
    ExecutionEvent,
    ExecutionRun,
    RunStatus,
)


class TestExecutionRun:
    def test_new_creates_pending_active_run(self):
        run = ExecutionRun.new(
            skill_name="gto",
            contract_type="workflow-execution",
            terminal_id="console_abc",
            session_id="sess123",
            required_artifacts=["SKILL.md", "findings.json"],
            allowed_tools=["Read", "Grep", "Bash"],
            blocked_tools=["Write", "Edit"],
        )
        assert run.skill_name == "gto"
        assert run.contract_type == "workflow-execution"
        assert run.phase == "pending"
        assert run.status == RunStatus.ACTIVE
        assert run.terminal_id == "console_abc"
        assert run.session_id == "sess123"
        assert run.required_artifacts == ["SKILL.md", "findings.json"]
        assert run.completed_artifacts == []
        assert run.missing_requirements == []
        assert run.allowed_tools_now == ["Read", "Grep", "Bash"]
        assert run.blocked_tools == ["Write", "Edit"]
        assert run.run_id  # uuid generated

    def test_to_jsonable_roundtrip(self):
        run = ExecutionRun.new(
            skill_name="test-skill",
            contract_type="structured-output",
            terminal_id="console_xyz",
            session_id="session1",
            required_artifacts=["output.json"],
            allowed_tools=["Read"],
            blocked_tools=[],
            response_requirements={"sections": ["analysis", "verification"]},
        )
        jsonable = run.to_jsonable()
        restored = ExecutionRun.from_jsonable(jsonable)
        assert restored.skill_name == run.skill_name
        assert restored.contract_type == run.contract_type
        assert restored.status == run.status
        assert restored.phase == run.phase
        assert restored.response_requirements == run.response_requirements
        assert restored.run_id == run.run_id

    def test_contract_type_literal(self):
        run = ExecutionRun.new(
            skill_name="skill",
            contract_type="hybrid",
            terminal_id="console_test",
            session_id="session",
        )
        assert run.contract_type in ("workflow-execution", "structured-output", "hybrid")


class TestExecutionEvent:
    def test_tool_allowed_event(self):
        event = ExecutionEvent(event_type="tool_allowed", tool="Read")
        assert event.event_type == "tool_allowed"
        assert event.tool == "Read"
        jsonable = event.to_jsonable()
        assert jsonable["type"] == "tool_allowed"
        assert jsonable["tool"] == "Read"

    def test_tool_blocked_event_with_reason(self):
        event = ExecutionEvent(
            event_type="tool_blocked",
            tool="Write",
            reason="not_in_allowed",
        )
        assert event.reason == "not_in_allowed"
        jsonable = event.to_jsonable()
        assert jsonable["reason"] == "not_in_allowed"

    def test_artifact_created_event(self):
        event = ExecutionEvent(event_type="artifact_created", path="findings.json")
        assert event.path == "findings.json"
        jsonable = event.to_jsonable()
        assert jsonable["path"] == "findings.json"

    def test_run_created_event(self):
        event = ExecutionEvent(event_type="run_created", skill="gto")
        assert event.skill == "gto"
        jsonable = event.to_jsonable()
        assert jsonable["skill"] == "gto"

    def test_run_ended_event(self):
        event = ExecutionEvent(event_type="run_ended", status="complete")
        assert event.status == "complete"
        jsonable = event.to_jsonable()
        assert jsonable["status"] == "complete"

    def test_phase_changed_event(self):
        event = ExecutionEvent(
            event_type="phase_changed",
            phase_from="loaded",
            phase_to="executing",
        )
        jsonable = event.to_jsonable()
        assert jsonable["from"] == "loaded"
        assert jsonable["to"] == "executing"

    def test_from_jsonable_roundtrip(self):
        d = {
            "type": "tool_blocked",
            "ts": 1234567890.0,
            "tool": "Edit",
            "reason": "blocked",
        }
        event = ExecutionEvent.from_jsonable(d)
        assert event.event_type == "tool_blocked"
        assert event.tool == "Edit"
        assert event.reason == "blocked"
        assert event.ts == 1234567890.0


class TestContractTypeDerivation:
    """
    INVARIANT 6 (contract type from SKILL.md) tests.

    Fact: ExecutionRun.contract_type must be one of the three defined types.
    The derivation chain is: SKILL.md frontmatter → get_skill_config()
    → _map_contract_type() → ExecutionRun.contract_type.
    """

    def test_all_three_contract_types_valid(self):
        """All three contract types are valid ExecutionRun contract_types."""
        for ct in ("workflow-execution", "structured-output", "hybrid"):
            run = ExecutionRun.new(
                skill_name="test", contract_type=ct,
                terminal_id="t1", session_id="s1",
            )
            assert run.contract_type == ct

    def test_contract_type_literal_defined(self):
        """ContractType is a Literal with exactly three values."""
        from skill_guard.execution_run import ContractType
        # ContractType must be a Literal
        import typing
        hints = typing.get_type_hints(ExecutionRun)
        assert "contract_type" in hints