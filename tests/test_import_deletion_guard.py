#!/usr/bin/env python3
r"""Tests for skill_guard.PreToolUse.PreToolUse_import_deletion_guard.

Covers:
    - _resolve_session_id: field name variants, env fallback, empty data
    - _parse_transcript_for_evidence: missing path, missing file, user prompt
      extraction, tool events, system-reminder skip, multiple tools
    - has_bypass_flag: no transcript, bypass present/absent, direct user_message
    - evaluate: allow/block based on evidence store and search evidence,
      bypass flag, non-python files, non-edit tools, no imports removed
    - extract_import_symbols: from import, multiple, bare import, import as,
      from import as
    - extract_removed_symbols: symbols removed, nothing removed
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the skill_guard package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skill_guard.PreToolUse.PreToolUse_import_deletion_guard import (
    _parse_transcript_for_evidence,
    _resolve_session_id,
    evaluate,
    extract_import_symbols,
    extract_removed_symbols,
    has_bypass_flag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transcript(lines: list[dict], tmp: str) -> str:
    """Write JSONL entries to a transcript file under *tmp* and return its path."""
    path = os.path.join(tmp, "transcript.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for entry in lines:
            fh.write(json.dumps(entry) + "\n")
    return path


def _grep_event(pattern: str, **extra) -> dict:
    """Build a Grep tool_use event for transcript or evidence store."""
    return {"name": "Grep", "pattern": pattern, **extra}


def _bash_event(command: str, **extra) -> dict:
    """Build a Bash tool_use event."""
    return {"name": "Bash", "command": command, **extra}


def _assistant_tool_use_message(*tool_events: dict) -> dict:
    """Build an assistant message containing tool_use blocks."""
    content = [
        {"type": "tool_use", "name": ev["name"], "input": ev, "id": f"call_{i}"}
        for i, ev in enumerate(tool_events)
    ]
    return {"role": "assistant", "type": "message", "message": {"content": content}}


def _user_message(text: str) -> dict:
    """Build a user message entry."""
    return {
        "role": "user",
        "type": "message",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _system_reminder(text: str) -> dict:
    """Build a system-reminder entry that should be skipped."""
    return {
        "role": "user",
        "type": "system-reminder",
        "message": {"content": [{"type": "text", "text": text}]},
    }


# ===================================================================
# TestResolveSessionId
# ===================================================================


class TestResolveSessionId:
    """_resolve_session_id checks multiple field names and env fallback."""

    def test_snake_case_session_id(self) -> None:
        assert _resolve_session_id({"session_id": "abc-123"}) == "abc-123"

    def test_camel_case_session_id(self) -> None:
        assert _resolve_session_id({"sessionId": "xyz-456"}) == "xyz-456"

    def test_conversation_id(self) -> None:
        assert _resolve_session_id({"conversation_id": "conv-1"}) == "conv-1"

    def test_conversation_id_camel(self) -> None:
        assert _resolve_session_id({"conversationId": "conv-2"}) == "conv-2"

    def test_env_fallback(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "env-session"}, clear=False):
            assert _resolve_session_id({}) == "env-session"

    def test_empty_returns_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            # Remove CLAUDE_SESSION_ID if set
            os.environ.pop("CLAUDE_SESSION_ID", None)
            assert _resolve_session_id({}) == ""

    def test_priority_over_env(self) -> None:
        """session_id field takes priority over CLAUDE_SESSION_ID env."""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "env-val"}, clear=False):
            assert _resolve_session_id({"session_id": "field-val"}) == "field-val"


# ===================================================================
# TestParseTranscriptForEvidence
# ===================================================================


class TestParseTranscriptForEvidence:
    """_parse_transcript_for_evidence reads JSONL transcript for user prompt
    and tool events."""

    def test_no_transcript_path_returns_empty(self) -> None:
        prompt, events = _parse_transcript_for_evidence({})
        assert prompt == ""
        assert events == []

    def test_missing_file_returns_empty(self) -> None:
        prompt, events = _parse_transcript_for_evidence(
            {"transcript_path": "/nonexistent/path/transcript.jsonl"}
        )
        assert prompt == ""
        assert events == []

    def test_user_prompt_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                _assistant_tool_use_message(_grep_event("MySymbol")),
                _user_message("Please refactor the module"),
            ]
            path = _make_transcript(lines, tmp)
            prompt, events = _parse_transcript_for_evidence(
                {"transcript_path": path}
            )
            assert prompt == "Please refactor the module"

    def test_tool_events_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            grep_ev = _grep_event("FooBar")
            bash_ev = _bash_event("grep -r FooBar --include='*.py'")
            lines = [
                _user_message("Remove unused imports"),
                _assistant_tool_use_message(grep_ev, bash_ev),
            ]
            path = _make_transcript(lines, tmp)
            prompt, events = _parse_transcript_for_evidence(
                {"transcript_path": path}
            )
            assert len(events) == 2
            assert events[0]["name"] == "Grep"
            assert "FooBar" in events[0].get("pattern", "")

    def test_system_reminder_skipped(self) -> None:
        """system-reminder entries should not be treated as user prompts."""
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                _user_message("Real user message"),
                _system_reminder("System reminder content"),
            ]
            path = _make_transcript(lines, tmp)
            prompt, events = _parse_transcript_for_evidence(
                {"transcript_path": path}
            )
            assert prompt == "Real user message"

    def test_multiple_tools_in_single_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ev1 = _grep_event("SymbolA")
            ev2 = _grep_event("SymbolB")
            ev3 = _bash_event("rg SymbolC")
            lines = [
                _user_message("cleanup"),
                _assistant_tool_use_message(ev1, ev2, ev3),
            ]
            path = _make_transcript(lines, tmp)
            prompt, events = _parse_transcript_for_evidence(
                {"transcript_path": path}
            )
            assert len(events) == 3
            names = [e["name"] for e in events]
            assert names.count("Grep") == 2
            assert names.count("Bash") == 1


# ===================================================================
# TestHasBypassFlag
# ===================================================================


class TestHasBypassFlag:
    """has_bypass_flag checks for --allow-import-removal in user prompt."""

    def test_no_transcript_no_direct_field(self) -> None:
        assert has_bypass_flag({}) is False

    def test_with_bypass_in_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                _user_message("Remove this import --allow-import-removal please"),
            ]
            path = _make_transcript(lines, tmp)
            assert has_bypass_flag({"transcript_path": path}) is True

    def test_without_bypass_in_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                _user_message("Just a normal message"),
            ]
            path = _make_transcript(lines, tmp)
            assert has_bypass_flag({"transcript_path": path}) is False

    def test_direct_user_message_field(self) -> None:
        """Fast path: user_message field directly contains bypass."""
        assert (
            has_bypass_flag({"user_message": "--allow-import-removal"})
            is True
        )

    def test_direct_user_message_without_bypass(self) -> None:
        assert has_bypass_flag({"user_message": "normal message"}) is False


# ===================================================================
# TestEvaluateTranscriptFallback
# ===================================================================


class TestEvaluateTranscriptFallback:
    """evaluate() allow/block decisions with evidence store mocked away."""

    @pytest.fixture(autouse=True)
    def _enable_guard(self) -> None:
        """Ensure the guard is enabled during tests."""
        with patch.dict(
            os.environ,
            {"IMPORT_DELETION_GUARD_ENABLED": "true"},
            clear=False,
        ):
            # Patch the module-level ENABLED flag
            from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

            original = mod.ENABLED
            mod.ENABLED = True
            yield
            mod.ENABLED = original

    @staticmethod
    def _edit_data(
        old_string: str,
        new_string: str,
        file_path: str = "src/module.py",
        user_message: str = "",
        tool_events: list[dict] | None = None,
    ) -> dict:
        """Build a minimal evaluate() payload for an Edit tool call."""
        data: dict = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
            "user_message": user_message,
            "session_id": "test-session",
            "terminal_id": "test-terminal",
        }
        return data

    def test_allows_when_symbol_searched_via_transcript(self) -> None:
        """Allows edit when Grep event for the removed symbol is found."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            mock_load.return_value = [_grep_event("UnusedClass")]
            data = self._edit_data(
                old_string="from myapp.models import UnusedClass\n",
                new_string="",
            )
            result = evaluate(data)
            assert result is None  # allowed

    def test_blocks_when_no_search_no_evidence(self) -> None:
        """Blocks edit when no evidence store events available and imports are removed."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            mock_load.return_value = None  # evidence store unavailable
            data = self._edit_data(
                old_string="from myapp.models import UnusedClass\n",
                new_string="",
            )
            result = evaluate(data)
            assert result is not None
            assert result.get("continue") is False
            assert "UnusedClass" in result.get("reason", "")

    def test_allows_with_bypass_flag_in_transcript(self) -> None:
        """Allows edit when has_bypass_flag returns True."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=True):
            mock_load.return_value = None
            data = self._edit_data(
                old_string="from myapp.models import UnusedClass\n",
                new_string="",
                user_message="--allow-import-removal",
            )
            result = evaluate(data)
            assert result is None  # bypassed

    def test_allows_non_python_files(self) -> None:
        """Non-.py files are never checked."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            mock_load.return_value = None
            data = self._edit_data(
                old_string="import os\n",
                new_string="",
                file_path="src/config.json",
            )
            result = evaluate(data)
            assert result is None  # not a .py file

    def test_allows_non_edit_tools(self) -> None:
        """Tools other than Edit/Write/MultiEdit are allowed."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            mock_load.return_value = None
            data = {
                "tool_name": "Read",
                "tool_input": {"file_path": "src/module.py"},
                "user_message": "",
                "session_id": "test",
                "terminal_id": "test",
            }
            result = evaluate(data)
            assert result is None

    def test_allows_when_no_imports_removed(self) -> None:
        """Allows edit when old and new strings have the same imports."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            mock_load.return_value = []
            data = self._edit_data(
                old_string="from myapp.models import User\n",
                new_string="from myapp.models import User\n\n# added comment\n",
            )
            result = evaluate(data)
            assert result is None  # no imports actually removed

    def test_blocks_when_symbol_not_searched(self) -> None:
        """Blocks edit when imports removed but no grep for those symbols."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        with patch.object(mod, "load_this_turn_events") as mock_load, \
             patch.object(mod, "has_bypass_flag", return_value=False):
            # Grep searched for something else, not UnusedClass
            mock_load.return_value = [_grep_event("SomeOtherSymbol")]
            data = self._edit_data(
                old_string="from myapp.models import UnusedClass\n",
                new_string="",
            )
            result = evaluate(data)
            assert result is not None
            assert result.get("continue") is False
            assert "UnusedClass" in result.get("reason", "")

    def test_disabled_guard_returns_none(self) -> None:
        """When IMPORT_DELETION_GUARD_ENABLED=false, always allow."""
        from skill_guard.PreToolUse import PreToolUse_import_deletion_guard as mod

        original = mod.ENABLED
        mod.ENABLED = False
        try:
            data = self._edit_data(
                old_string="from myapp.models import UnusedClass\n",
                new_string="",
            )
            result = evaluate(data)
            assert result is None
        finally:
            mod.ENABLED = original


# ===================================================================
# TestExtractImportSymbols
# ===================================================================


class TestExtractImportSymbols:
    """extract_import_symbols parses various import statement forms."""

    def test_from_import(self) -> None:
        symbols = extract_import_symbols("from collections import OrderedDict\n")
        assert symbols == {"OrderedDict"}

    def test_multiple_from_import(self) -> None:
        symbols = extract_import_symbols("from os.path import join, exists, isfile\n")
        assert symbols == {"join", "exists", "isfile"}

    def test_bare_import(self) -> None:
        symbols = extract_import_symbols("import os\n")
        assert symbols == {"os"}

    def test_import_as(self) -> None:
        symbols = extract_import_symbols("import numpy as np\n")
        assert "numpy" in symbols

    def test_from_import_as(self) -> None:
        symbols = extract_import_symbols("from collections import OrderedDict as OD\n")
        assert "OrderedDict" in symbols

    def test_multiline_parenthesized(self) -> None:
        text = "from mymodule import (\n    Foo,\n    Bar,\n    Baz,\n)\n"
        symbols = extract_import_symbols(text)
        assert symbols == {"Foo", "Bar", "Baz"}

    def test_multiple_bare_imports_on_one_line(self) -> None:
        symbols = extract_import_symbols("import os, sys, re\n")
        assert symbols == {"os", "sys", "re"}

    def test_empty_string(self) -> None:
        assert extract_import_symbols("") == set()

    def test_no_imports(self) -> None:
        text = "def foo():\n    pass\n"
        assert extract_import_symbols(text) == set()


    def test_multiline_mixed_with_code(self) -> None:
        """Multiline parenthesized import mixed with non-import code."""
        text = "import os\n\nfrom mymodule import (\n    Alpha,\n    Beta,\n)\n\ndef hello():\n    pass\n"
        symbols = extract_import_symbols(text)
        assert symbols == {"os", "Alpha", "Beta"}

    def test_parenthesized_spanning_many_lines(self) -> None:
        """Parenthesized import spanning 5+ lines with trailing comma."""
        text = "from deep.package import (\n    ClassA,\n    ClassB,\n    ClassC,\n    ClassD,\n)\n"
        symbols = extract_import_symbols(text)
        assert symbols == {"ClassA", "ClassB", "ClassC", "ClassD"}

    def test_single_line_parenthesized_explicit(self) -> None:
        """Single-line parenthesized import still works."""
        text = "from mymodule import (Foo, Bar)\n"
        symbols = extract_import_symbols(text)
        assert symbols == {"Foo", "Bar"}

# ===================================================================
# TestExtractRemovedSymbols
# ===================================================================


class TestExtractRemovedSymbols:
    """extract_removed_symbols computes set difference of import symbols."""

    def test_removed(self) -> None:
        old = "from myapp.models import User, Post, Comment\n"
        new = "from myapp.models import User, Post\n"
        removed = extract_removed_symbols(old, new)
        assert removed == {"Comment"}

    def test_nothing_removed(self) -> None:
        old = "import os\nimport sys\n"
        new = "import os\nimport sys\n\n# comment added\n"
        removed = extract_removed_symbols(old, new)
        assert removed == set()

    def test_all_removed(self) -> None:
        old = "from typing import List, Dict\n"
        new = ""
        removed = extract_removed_symbols(old, new)
        assert removed == {"List", "Dict"}

    def test_added_imports_not_flagged(self) -> None:
        old = "from myapp.models import User\n"
        new = "from myapp.models import User, Post\n"
        removed = extract_removed_symbols(old, new)
        assert removed == set()
