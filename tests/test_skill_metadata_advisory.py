from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest


def _make_context(prompt: str, session_id: str = "session-1") -> MagicMock:
    ctx = MagicMock()
    ctx.prompt = prompt
    ctx.session_id = session_id
    ctx.data = {"userMessage": prompt, "session_id": session_id}
    return ctx


class _Context:
    def __init__(self, prompt: str, session_id: str = "session-1") -> None:
        self.prompt = prompt
        self.session_id = session_id
        self.data = {"userMessage": prompt, "session_id": session_id}


def test_skill_metadata_advisory_flags_undercontracted_skill(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {"workflow_steps": ["one"], "enforcement": "advisory"},
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    result = advisory.skill_metadata_advisory(_Context("/decision-tree evaluate tradeoffs"))

    assert result is not None
    assert "undercontracted" in result.lower()
    assert "decision-tree" in captured.get("source", "")


def test_skill_metadata_advisory_clears_hardened_skill(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow",
            "enforcement": "strict",
            "workflow_steps": ["one"],
            "workflow_binding": "exclusive",
            "workflow_enforcement": "hard",
            "required_phase_artifacts": ["artifact"],
        },
    )

    result = advisory.skill_metadata_advisory(_Context("/retro review the session"))

    assert result is None


# -------------------------------------------------------------------
# Migration status advisory tests
# -------------------------------------------------------------------

def test_migration_advisory_emits_notification_for_unmigrated(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "enforcement": "advisory",
            "description": "A legacy skill",
        },
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    result = advisory.skill_metadata_advisory(_Context("/old-skill run"))

    # Should emit a warning notification for UNMIGRATED skill
    assert captured.get("notification_type") == "warning"
    assert "legacy" in captured.get("message", "").lower()
    assert captured.get("source") == "skill_metadata_advisory:old-skill"
    assert "migrate-skill-ef" in captured.get("message", "")
    assert captured.get("priority") == 1


def test_migration_advisory_emits_info_notification_for_partially_migrated(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow-execution",
            "allowed_tools_now": ["Bash"],
            # missing required_artifacts
        },
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    result = advisory.skill_metadata_advisory(_Context("/half-migrated run"))

    # Should emit an info notification for PARTIALLY_MIGRATED skill
    assert captured.get("notification_type") == "info"
    assert "incomplete" in captured.get("message", "").lower()
    assert captured.get("source") == "skill_metadata_advisory:half-migrated"
    assert "migrate-skill-ef" in captured.get("message", "")
    assert captured.get("priority") == 1


def test_migration_advisory_silent_for_migrated(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured_calls = []
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow-execution",
            "required_artifacts": ["output.json"],
            "allowed_tools_now": ["Bash", "Read"],
        },
    )
    monkeypatch.setattr(
        advisory, "add_notification", lambda **kwargs: captured_calls.append(kwargs)
    )

    result = advisory.skill_metadata_advisory(_Context("/migrated-skill run"))

    # No migration notification emitted for MIGRATED skill
    migration_calls = [
        c for c in captured_calls
        if "migration" in c.get("source", "") or c.get("message", "").startswith("Skill '/migrated-skill'")
    ]
    assert migration_calls == [], f"Expected no migration notification, got: {migration_calls}"


def test_migration_advisory_unmigrated_with_legacy_workflow_type(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow",  # legacy, not contract-era
            "workflow_steps": ["step one"],
        },
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    advisory.skill_metadata_advisory(_Context("/legacy-workflow run"))

    assert captured.get("notification_type") == "warning"
    assert "legacy-workflow" in captured.get("source", "")


def test_migration_advisory_unmigrated_no_contract_fields(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "enforcement": "none",
            "description": "No contract fields",
        },
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    advisory.skill_metadata_advisory(_Context("/bare-skill run"))

    assert captured.get("notification_type") == "warning"
    assert captured.get("source") == "skill_metadata_advisory:bare-skill"


def test_migration_advisory_partially_migrated_workflow_execution(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured = {}
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow-execution",
            "response_requirements": {"sections": ["a"]},
            # missing required_artifacts
        },
    )
    monkeypatch.setattr(advisory, "add_notification", lambda **kwargs: captured.update(kwargs))

    advisory.skill_metadata_advisory(_Context("/wf-exec-missing run"))

    assert captured.get("notification_type") == "info"
    assert "incomplete" in captured.get("message", "").lower()


def test_migration_advisory_silent_for_knowledge_skill(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured_calls = []
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "category": "knowledge",
            "contract_type": "analysis",
            "description": "A knowledge reference",
        },
    )
    monkeypatch.setattr(
        advisory, "add_notification", lambda **kwargs: captured_calls.append(kwargs)
    )

    advisory.skill_metadata_advisory(_Context("/search run"))

    migration_calls = [
        c for c in captured_calls
        if "skill_metadata_advisory:search" in c.get("source", "")
        and "enhancement" not in c.get("source", "")
    ]
    assert migration_calls == [], f"Expected no migration notification for knowledge skill, got: {migration_calls}"


def test_migration_advisory_silent_when_metadata_is_none(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured_calls = []
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: None,  # skill file not found
    )
    monkeypatch.setattr(
        advisory, "add_notification", lambda **kwargs: captured_calls.append(kwargs)
    )

    advisory.skill_metadata_advisory(_Context("/unknown-skill run"))

    migration_calls = [
        c for c in captured_calls
        if "skill_metadata_advisory:unknown-skill" in c.get("source", "")
        and "enhancement" not in c.get("source", "")
    ]
    assert migration_calls == [], f"Expected no migration notification when metadata is None, got: {migration_calls}"


def test_migration_advisory_silent_for_known_knowledge_skill_name(monkeypatch):
    advisory = importlib.import_module("skill_guard.skill_metadata_advisory")

    captured_calls = []
    # "search" is in KNOWLEDGE_SKILLS even without category: knowledge
    monkeypatch.setattr(
        advisory,
        "_load_skill_frontmatter",
        lambda skill_name: {
            "contract_type": "workflow",
            "workflow_steps": ["one"],
        },
    )
    monkeypatch.setattr(
        advisory, "add_notification", lambda **kwargs: captured_calls.append(kwargs)
    )

    advisory.skill_metadata_advisory(_Context("/search run"))

    migration_calls = [
        c for c in captured_calls
        if "skill_metadata_advisory:search" in c.get("source", "")
        and "enhancement" not in c.get("source", "")
    ]
    assert migration_calls == [], f"Expected no migration notification for KNOWLEDGE_SKILLS entry, got: {migration_calls}"
