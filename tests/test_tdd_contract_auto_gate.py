from __future__ import annotations

import importlib


class _Context:
    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        self.session_id = "session-1"
        self.terminal_id = "terminal-1"
        self.data = {}


class _Manager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.existing = None

    def get_phase(self, target_file: str):
        self.calls.append(("get_phase", target_file))
        return self.existing

    def set_phase(self, target_file: str, phase: str):
        self.calls.append(("set_phase", f"{target_file}:{phase}"))


def test_tdd_contract_auto_gate_sets_red_phase(monkeypatch):
    tdd_gate = importlib.import_module("skill_guard.tdd_contract_auto_gate")

    manager = _Manager()
    monkeypatch.setattr(tdd_gate, "_get_tdd_manager", lambda context: manager)

    assert tdd_gate.tdd_contract_auto_gate(_Context("/code src/example.py")) is True
    assert manager.calls == [("get_phase", "src/example.py"), ("set_phase", "src/example.py:red")]


def test_tdd_contract_auto_gate_honors_bypass(monkeypatch):
    tdd_gate = importlib.import_module("skill_guard.tdd_contract_auto_gate")

    monkeypatch.setenv("TDD_CONTRACT_BYPASS", "1")
    assert tdd_gate.tdd_contract_auto_gate(_Context("/code src/example.py")) is False
