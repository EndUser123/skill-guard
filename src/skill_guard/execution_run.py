"""
execution_run.py
================

Data model for the skill-guard execution contract runtime.

Defines:
- ContractType: Literal["workflow-execution", "structured-output", "hybrid"]
- RunStatus: ACTIVE | COMPLETE | FAILED
- ExecutionEvent: one line in execution-events.jsonl
- ExecutionRun: the full run state
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


ContractType = Literal["workflow-execution", "structured-output", "hybrid"]


class RunStatus:
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ExecutionEvent:
    """One event in the append-only execution-events.jsonl."""

    event_type: str
    ts: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    # Optional fields for specific event types
    skill: str | None = None
    tool: str | None = None
    reason: str | None = None
    path: str | None = None
    phase_from: str | None = None
    phase_to: str | None = None
    status: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.event_type, "ts": self.ts}
        if self.skill is not None:
            d["skill"] = self.skill
        if self.tool is not None:
            d["tool"] = self.tool
        if self.reason is not None:
            d["reason"] = self.reason
        if self.path is not None:
            d["path"] = self.path
        if self.phase_from is not None:
            d["from"] = self.phase_from
        if self.phase_to is not None:
            d["to"] = self.phase_to
        if self.status is not None:
            d["status"] = self.status
        return d

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> ExecutionEvent:
        return cls(
            event_type=d["type"],
            ts=d.get("ts", datetime.now(timezone.utc).timestamp()),
            skill=d.get("skill"),
            tool=d.get("tool"),
            reason=d.get("reason"),
            path=d.get("path"),
            phase_from=d.get("from"),
            phase_to=d.get("to"),
            status=d.get("status"),
        )


@dataclass
class ExecutionRun:
    """The full execution run state stored in execution-state.json."""

    run_id: str
    skill_name: str
    contract_type: ContractType
    phase: str = "pending"
    status: str = RunStatus.ACTIVE
    terminal_id: str = ""
    session_id: str = ""

    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())

    required_artifacts: list[str] = field(default_factory=list)
    completed_artifacts: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)

    allowed_tools_now: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)

    # For structured-output / hybrid contract types
    response_requirements: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "skill_name": self.skill_name,
            "contract_type": self.contract_type,
            "phase": self.phase,
            "status": self.status,
            "terminal_id": self.terminal_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "required_artifacts": self.required_artifacts,
            "completed_artifacts": self.completed_artifacts,
            "missing_requirements": self.missing_requirements,
            "allowed_tools_now": self.allowed_tools_now,
            "blocked_tools": self.blocked_tools,
            "response_requirements": self.response_requirements,
        }

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> ExecutionRun:
        return cls(
            run_id=d["run_id"],
            skill_name=d["skill_name"],
            contract_type=d["contract_type"],
            phase=d.get("phase", "pending"),
            status=d.get("status", RunStatus.ACTIVE),
            terminal_id=d.get("terminal_id", ""),
            session_id=d.get("session_id", ""),
            created_at=d.get("created_at", datetime.now(timezone.utc).timestamp()),
            updated_at=d.get("updated_at", datetime.now(timezone.utc).timestamp()),
            required_artifacts=d.get("required_artifacts", []),
            completed_artifacts=d.get("completed_artifacts", []),
            missing_requirements=d.get("missing_requirements", []),
            allowed_tools_now=d.get("allowed_tools_now", []),
            blocked_tools=d.get("blocked_tools", []),
            response_requirements=d.get("response_requirements", {}),
        )

    @classmethod
    def new(
        cls,
        skill_name: str,
        contract_type: ContractType,
        terminal_id: str,
        session_id: str,
        required_artifacts: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        response_requirements: dict[str, Any] | None = None,
    ) -> ExecutionRun:
        now = datetime.now(timezone.utc).timestamp()
        return cls(
            run_id=str(uuid.uuid4()),
            skill_name=skill_name,
            contract_type=contract_type,
            phase="pending",
            status=RunStatus.ACTIVE,
            terminal_id=terminal_id,
            session_id=session_id,
            created_at=now,
            updated_at=now,
            required_artifacts=required_artifacts or [],
            completed_artifacts=[],
            missing_requirements=[],
            allowed_tools_now=allowed_tools or [],
            blocked_tools=blocked_tools or [],
            response_requirements=response_requirements or {},
        )