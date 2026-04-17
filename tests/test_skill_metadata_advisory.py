from __future__ import annotations

import importlib


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
    assert captured["source"] == "skill_metadata_advisory:decision-tree"


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
    monkeypatch.setattr(advisory, "clear_by_type", lambda *args, **kwargs: captured.update(kwargs) or 1)

    result = advisory.skill_metadata_advisory(_Context("/retro review the session"))

    assert result is None
    assert captured["source"] == "skill_metadata_advisory:retro"
