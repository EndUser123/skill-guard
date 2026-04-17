from __future__ import annotations

import importlib


class _Context:
    def __init__(self) -> None:
        self.prompt = "/arch do the thing"
        self.session_id = "session-1"
        self.terminal_id = "terminal-1"
        self.data = {}


def test_ensure_turn_marker_creates_and_stores_turn(monkeypatch):
    turn_marker = importlib.import_module("skill_guard.turn_marker")

    context = _Context()
    monkeypatch.setattr(turn_marker, "get_active_turn", lambda session_id, terminal_id: None)
    monkeypatch.setattr(
        turn_marker,
        "start_turn",
        lambda **kwargs: "turn-123",
    )

    turn_id = turn_marker.ensure_turn_marker(context)

    assert turn_id == "turn-123"
    assert context.data["turn_id"] == "turn-123"


def test_ensure_turn_marker_skips_without_terminal():
    turn_marker = importlib.import_module("skill_guard.turn_marker")

    context = _Context()
    context.terminal_id = ""

    assert turn_marker.ensure_turn_marker(context) is None
