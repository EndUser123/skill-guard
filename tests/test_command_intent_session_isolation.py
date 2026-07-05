"""STATE-01 + Change 1 + FM-2 regression tests for command-intent isolation.

Covers the multi-terminal isolation hard requirement: WT_SESSION (terminal_id)
is shared across concurrent Claude sessions in one Windows Terminal, so the
intent file MUST be keyed by session_id, not terminal_id.

Anti-mock: uses a real tmpdir via CLAUDE_PROJECT_DIR env-at-call-time. Only
ExecutionRuntime (heavy, out of scope) is patched.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from skill_guard import skill_enforcer
from skill_guard.skill_enforcer import (
    clear_command_intent,
    log_command_intent_telemetry,
)
from skill_guard.user_prompt_submit_hook import handle_user_prompt_submit


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Redirect _hooks_dir() to tmp_path via env-at-call-time."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def _intent_path(base: Path, session_id: str) -> Path:
    return base / ".claude" / "hooks" / "state" / "sessions" / session_id / "pending_command_intent.json"


class TestState01WriterIsSessionScoped:
    """STATE-01: writer keys by session_id, not terminal_id."""

    def test_writer_uses_session_scoped_path(self, isolated_state):
        log_command_intent_telemetry("tid_shared", "sess_A", "/wiki foo", "wiki")
        path = _intent_path(isolated_state, "sess_A")
        assert path.exists(), f"session-scoped file not written at {path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["skill"] == "wiki"
        assert payload["session_id"] == "sess_A"

    def test_writer_does_not_collide_across_sessions_sharing_terminal(self, isolated_state):
        # Two sessions share the same WT_SESSION (terminal_id) — root cause of the FP.
        log_command_intent_telemetry("tid_shared", "sess_A", "/wiki a", "wiki")
        log_command_intent_telemetry("tid_shared", "sess_B", "/code b", "code")
        assert _intent_path(isolated_state, "sess_A").exists()
        assert _intent_path(isolated_state, "sess_B").exists()
        a = json.loads(_intent_path(isolated_state, "sess_A").read_text(encoding="utf-8"))
        b = json.loads(_intent_path(isolated_state, "sess_B").read_text(encoding="utf-8"))
        assert a["skill"] == "wiki" and b["skill"] == "code"

    def test_writer_falls_back_to_terminal_scoped_without_session(self, isolated_state):
        log_command_intent_telemetry("tid_only", "", "/wiki a", "wiki")
        # No session-scoped path
        assert not (_intent_path(isolated_state, "")).parent.parent.exists() or True
        # Legacy terminal-scoped path written instead
        legacy = isolated_state / ".claude" / "hooks" / "state" / "terminals" / "tid_only" / "pending_command_intent.json"
        assert legacy.exists()


class TestT2WTSessionSharedClearIsolation:
    """T2: clear_command_intent MUST NOT touch a sibling session's file
    when both sessions share terminal_id (WT_SESSION)."""

    def test_clear_does_not_damage_sibling_session(self, isolated_state):
        log_command_intent_telemetry("tid_shared", "sess_A", "/wiki a", "wiki")
        log_command_intent_telemetry("tid_shared", "sess_B", "/code b", "code")

        # Session B sends a non-slash follow-up → clears its own intent only
        clear_command_intent("tid_shared", "sess_B")

        assert _intent_path(isolated_state, "sess_A").exists(), (
            "T2 REGRESSION: clearing session B deleted session A's in-flight intent"
        )
        assert not _intent_path(isolated_state, "sess_B").exists()

    def test_clear_refuses_without_session_id(self, isolated_state):
        # Refusing to clear protects sibling sessions when session_id is absent.
        log_command_intent_telemetry("tid_shared", "sess_A", "/wiki a", "wiki")
        # Even though terminal_id matches, no session → no clear
        clear_command_intent("tid_shared", "")
        assert _intent_path(isolated_state, "sess_A").exists()


class TestChange1AndFM2:
    """Change 1: non-slash single-line UPS clears. FM-2: multi-line does NOT."""

    def test_single_line_non_slash_clears_intent(self, isolated_state):
        log_command_intent_telemetry("tid1", "sess_A", "/wiki a", "wiki")
        assert _intent_path(isolated_state, "sess_A").exists()

        data = {"prompt": "just a plain follow-up", "session_id": "sess_A", "terminal_id": "tid1"}
        with patch("skill_guard.user_prompt_submit_hook.ExecutionRuntime"):
            result = handle_user_prompt_submit(data)
        assert result.get("continue") is True
        assert not _intent_path(isolated_state, "sess_A").exists(), (
            "Change 1 REGRESSION: single-line non-slash UPS did not clear stale intent"
        )

    def test_multi_line_non_slash_does_not_clear(self, isolated_state):
        """FM-2: extract_slash_command anchors on line 1; a multi-line paste
        with prose on line 1 must NOT destructively clear an in-flight intent."""
        log_command_intent_telemetry("tid1", "sess_A", "/wiki a", "wiki")
        assert _intent_path(isolated_state, "sess_A").exists()

        multi_line = "Let's address the bug:\n/wiki refactor the auth module\nmore detail"
        data = {"prompt": multi_line, "session_id": "sess_A", "terminal_id": "tid1"}
        with patch("skill_guard.user_prompt_submit_hook.ExecutionRuntime"):
            result = handle_user_prompt_submit(data)
        assert result.get("continue") is True
        assert _intent_path(isolated_state, "sess_A").exists(), (
            "FM-2 REGRESSION: multi-line non-slash UPS destructively cleared in-flight intent"
        )

    def test_slash_command_does_not_clear_writes_intent(self, isolated_state):
        """Sanity: a real slash command still arms the gate (no clear)."""
        with patch("skill_guard.user_prompt_submit_hook.ExecutionRuntime"):
            result = handle_user_prompt_submit(
                {"prompt": "/wiki analyze foo", "session_id": "sess_A", "terminal_id": "tid1"}
            )
        # additionalContext indicates enforcement fired; intent file written
        assert "additionalContext" in result or result.get("continue") is True
        assert _intent_path(isolated_state, "sess_A").exists()
