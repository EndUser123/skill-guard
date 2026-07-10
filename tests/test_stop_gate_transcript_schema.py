r"""Regression tests: Stop gate vs the CURRENT transcript schema.

Incident (2026-07-09, session 8c279c46): user typed `/cc-skills-sdlc:go proceed`,
the assistant answered "No response required." with ZERO tool calls, and the
skill-execution Stop gate did not fire. Root cause: the transcript parser read
`entry["role"]` at top level, but the current schema nests role under
`message.role` (top-level `type: "user"`), so every user message was invisible,
`slash_cmd` was always None, and the slash-command enforcement branch was
unreachable. Side effect: the reverse scan never found a turn boundary and
accumulated tool_use blocks from ALL prior turns.

These tests pin the current-schema behavior with real-format fixture entries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_guard import StopHook_skill_execution_gate as gate
from skill_guard.slash_command_observability import extract_slash_command


# --- Fixture builders: entries in the CURRENT transcript schema -------------

def _user(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _user_blocks(blocks: list) -> dict:
    return {"type": "user", "message": {"role": "user", "content": blocks}}


def _assistant(blocks: list) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}


def _command_entry(name: str, args: str) -> dict:
    return _user(
        f"<command-message>{name.lstrip('/')}</command-message>\n"
        f"<command-name>{name}</command-name>\n"
        f"<command-args>{args}</command-args>"
    )


def _write_transcript(tmp_path: Path, entries: list[dict]) -> str:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(p)


def _incident_entries() -> list[dict]:
    """Previous turn with a tool call, then the incident turn (zero tools)."""
    return [
        _user("earlier question"),
        _assistant(
            [
                {"type": "tool_use", "id": "t1", "name": "TaskUpdate", "input": {"taskId": "1"}},
            ]
        ),
        _user_blocks([{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]),
        _assistant([{"type": "text", "text": "previous turn answer"}]),
        _command_entry("/cc-skills-sdlc:go", "proceed"),
        _user("Base directory for this skill: P:...\n\n# /go - Evidence-First SDLC Orchestrator"),
        _assistant([{"type": "text", "text": "No response required."}]),
    ]


@pytest.fixture
def no_ledger(monkeypatch):
    """Isolate run() from ledger/state side channels."""
    monkeypatch.setattr(gate, "LEDGER_AVAILABLE", False)
    monkeypatch.setattr(gate, "ENABLED", True)
    monkeypatch.setattr(gate, "_read_state", lambda: {})
    monkeypatch.setattr(gate, "_get_terminal_id", lambda data: None)
    monkeypatch.setattr(gate, "_get_active_turn_id", lambda tid: None)


# --- Extraction --------------------------------------------------------------

def test_user_prompt_is_command_entry_not_skill_injection(tmp_path):
    snap = gate._parse_transcript_snapshot(
        {"transcript_path": _write_transcript(tmp_path, _incident_entries())}
    )
    assert "<command-name>/cc-skills-sdlc:go</command-name>" in snap["user_prompt"]
    assert "Base directory" not in snap["user_prompt"]


def test_nested_message_role_is_recognized(tmp_path):
    entries = [_user("plain question"), _assistant([{"type": "text", "text": "answer"}])]
    snap = gate._parse_transcript_snapshot({"transcript_path": _write_transcript(tmp_path, entries)})
    assert snap["user_prompt"] == "plain question"
    assert snap["response_text"] == "answer"


def test_tools_are_turn_scoped_not_whole_transcript(tmp_path):
    snap = gate._parse_transcript_snapshot(
        {"transcript_path": _write_transcript(tmp_path, _incident_entries())}
    )
    assert [t.get("name") for t in snap["tools_used"]] == []  # TaskUpdate is a prior turn


def test_extract_slash_command_xml_form():
    prompt = (
        "<command-message>cc-skills-sdlc:go</command-message>\n"
        "<command-name>/cc-skills-sdlc:go</command-name>\n"
        "<command-args>proceed</command-args>"
    )
    assert extract_slash_command(prompt) == ("cc-skills-sdlc:go", "proceed")


def test_extract_slash_command_plain_forms_unchanged():
    assert extract_slash_command("/go proceed") == ("go", "proceed")
    assert extract_slash_command("/cc-skills-utils:plugin-installer audit") == (
        "cc-skills-utils:plugin-installer",
        "audit",
    )
    assert extract_slash_command("just prose") == (None, "")


# --- Gate behavior (incident regression) -------------------------------------

def test_run_blocks_zero_tool_slash_turn(tmp_path, no_ledger):
    result = gate.run({"transcript_path": _write_transcript(tmp_path, _incident_entries())})
    assert result is not None and result.get("block") is True
    assert "cc-skills-sdlc:go" in result["reason"]


def test_run_allows_slash_turn_with_execution_tools(tmp_path, no_ledger):
    entries = [
        _command_entry("/cc-skills-sdlc:go", "proceed"),
        _user("Base directory for this skill: P:...\n\n# /go"),
        _assistant([{"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "ls"}}]),
        _user_blocks([{"type": "tool_result", "tool_use_id": "b1", "content": "ok"}]),
        _assistant([{"type": "text", "text": "done, ran the workflow"}]),
    ]
    result = gate.run({"transcript_path": _write_transcript(tmp_path, entries)})
    assert result is None


def test_run_exempts_namespaced_builtin_tail(tmp_path, no_ledger):
    entries = [
        _command_entry("/some-plugin:help", ""),
        _assistant([{"type": "text", "text": "here is help text"}]),
    ]
    result = gate.run({"transcript_path": _write_transcript(tmp_path, entries)})
    assert result is None  # "help" is a builtin tail — exempt even with zero tools


def test_is_exempt_command():
    assert gate._is_exempt_command(None) is True
    assert gate._is_exempt_command("help") is True
    assert gate._is_exempt_command("some-plugin:help") is True
    assert gate._is_exempt_command("cc-skills-sdlc:go") is False


# --- FP regression (2026-07-10): builtin command steal -------------------------
# /reload-plugins is CLI-handled and writes NO assistant entry, so its command
# entry sits contiguous with the next real user prompt. The scan must not steal
# it, and builtins must be exempt via the SHARED exemption sets.

def _friction_entries() -> list[dict]:
    return [
        _command_entry("/reload-plugins", ""),
        _user("do you know what to do with this packet?"),
        _assistant([{"type": "text", "text": "Yes. It's an adversarial-review packet..."}]),
    ]


def test_scan_does_not_steal_previous_turn_command_entry(tmp_path):
    snap = gate._parse_transcript_snapshot(
        {"transcript_path": _write_transcript(tmp_path, _friction_entries())}
    )
    assert snap["user_prompt"] == "do you know what to do with this packet?"


def test_run_allows_prose_turn_after_builtin_command(tmp_path, no_ledger):
    result = gate.run({"transcript_path": _write_transcript(tmp_path, _friction_entries())})
    assert result is None


def test_exemption_sets_are_shared_single_source():
    import skill_guard.slash_command_observability as obs

    assert gate.BUILTIN_SLASH_COMMANDS is obs.BUILTIN_SLASH_COMMANDS
    assert gate.LIGHTWEIGHT_SLASH_COMMANDS is obs.LIGHTWEIGHT_SLASH_COMMANDS
    assert gate._is_exempt_command("reload-plugins") is True
    assert gate._is_exempt_command("compact") is True


# --- Registered entry point (router.py Stop) ----------------------------------
# Pins testing_entrypoint_launch_gap: the gate module was orphaned — no entry
# point invoked run() — so module-level tests alone could never prove liveness.

ROUTER = Path(__file__).parents[1] / "src" / "skill_guard" / "__lib" / "router.py"


def _run_router_stop(transcript: str) -> dict:
    import subprocess
    import sys as _sys

    proc = subprocess.run(
        [_sys.executable, str(ROUTER), "Stop"],
        input=json.dumps({"transcript_path": transcript}),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_entrypoint_blocks_zero_tool_slash_turn(tmp_path):
    out = _run_router_stop(_write_transcript(tmp_path, _incident_entries()))
    assert out.get("decision") == "block"
    assert "cc-skills-sdlc:go" in out.get("reason", "")


def test_entrypoint_allows_execution_turn(tmp_path):
    entries = [
        _command_entry("/cc-skills-sdlc:go", "proceed"),
        _user("Base directory for this skill: P:...\n\n# /go"),
        _assistant([{"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "ls"}}]),
        _user_blocks([{"type": "tool_result", "tool_use_id": "b1", "content": "ok"}]),
        _assistant([{"type": "text", "text": "done, ran the workflow"}]),
    ]
    out = _run_router_stop(_write_transcript(tmp_path, entries))
    assert out == {}


# --- log_event append semantics ----------------------------------------------

def test_log_event_appends_instead_of_replacing(tmp_path, monkeypatch):
    log_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(gate, "LOG_FILE", log_file)
    gate.log_event("first", {"a": 1})
    gate.log_event("second", {"b": 2})
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first"
    assert json.loads(lines[1])["event"] == "second"


# --- Ledger fallback turn-scoping (fix 2a, 2026-07-10) ------------------------
# The transcript-parse-failure fallback must only honor a skill_loaded event
# from the ACTIVE turn. Before fix 2a it matched ANY historical skill_loaded
# for the terminal, so a zero-tool turn following any earlier skill use was
# silently allowed. The fallback is reached only via the PLAIN slash form (no
# <command-name> XML) with zero tools — the harness-XML path blocks earlier.

_CURRENT_TURN = "turn-current-2a"
_PRIOR_TURN = "turn-prior-2a"


def _plain_slash_zero_tool_entries() -> list[dict]:
    """Plain-form slash command (not harness-expanded); current turn has zero tools."""
    return [
        _user("/cc-skills-sdlc:go proceed"),
        _assistant([{"type": "text", "text": "I'll answer in prose instead of running it."}]),
    ]


def _enable_ledger(monkeypatch, active_turn: str) -> None:
    """Turn the ledger on with a resolved active turn, isolating state side channels."""
    monkeypatch.setattr(gate, "LEDGER_AVAILABLE", True)
    monkeypatch.setattr(gate, "ENABLED", True)
    monkeypatch.setattr(gate, "_read_state", lambda: {})
    monkeypatch.setattr(gate, "_get_terminal_id", lambda data: "term-2a")
    monkeypatch.setattr(gate, "_get_active_turn_id", lambda tid: active_turn)


def test_ledger_fallback_does_not_match_prior_turn_skill_loaded(tmp_path, monkeypatch):
    """Fix 2a: a PRIOR-turn skill_loaded must not satisfy the current-turn fallback."""
    import __lib.hook_ledger as ledger

    # Precondition: slash command is extracted from the plain form.
    assert extract_slash_command("/cc-skills-sdlc:go proceed") == ("cc-skills-sdlc:go", "proceed")

    # Current turn has NO skill_loaded; a PRIOR turn does. The old terminal-wide
    # match would have allowed the stop; the turn-scoped filter must not.
    def fake_load_db_events(turn_id):
        assert turn_id == _CURRENT_TURN, f"fallback must query active turn, got {turn_id!r}"
        return []

    prior_event = {
        "event_type": "skill_loaded",
        "turn_id": _PRIOR_TURN,
        "payload": {"skill": "cc-skills-sdlc:go", "turn_id": _PRIOR_TURN},
    }

    monkeypatch.setattr(ledger, "_load_db_events", fake_load_db_events)
    monkeypatch.setattr(ledger, "_load_db_skill_events", lambda terminal_id: [prior_event])
    _enable_ledger(monkeypatch, _CURRENT_TURN)

    result = gate.run({"transcript_path": _write_transcript(tmp_path, _plain_slash_zero_tool_entries())})

    # Prior-turn skill_loaded no longer satisfies the fallback → gate blocks.
    assert result is not None
    assert result.get("block") is True
    assert "cc-skills-sdlc:go" in result["reason"]


def test_ledger_fallback_still_allows_same_turn_skill_loaded(tmp_path, monkeypatch):
    """Positive control: a CURRENT-turn skill_loaded still satisfies the fallback."""
    import __lib.hook_ledger as ledger

    same_turn_event = {
        "event_type": "skill_loaded",
        "turn_id": _CURRENT_TURN,
        "payload": {"skill": "cc-skills-sdlc:go", "turn_id": _CURRENT_TURN},
    }

    monkeypatch.setattr(ledger, "_load_db_events", lambda turn_id: [same_turn_event])
    monkeypatch.setattr(ledger, "_load_db_skill_events", lambda terminal_id: [])
    _enable_ledger(monkeypatch, _CURRENT_TURN)

    result = gate.run({"transcript_path": _write_transcript(tmp_path, _plain_slash_zero_tool_entries())})
    assert result is None  # current-turn skill_loaded → fallback allows stop
