#!/usr/bin/env python3
"""Tests for load_tool_events_for_context terminal-scoped evidence filtering.

These tests verify that tool events are properly filtered by terminal_id
to prevent cross-terminal evidence contamination.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Mock function to be implemented - this is what we're testing
def load_tool_events_for_context(
    transcript_path: Path,
    terminal_id: str | None,
    turn_start_event_id: int,
) -> list[dict[str, Any]]:
    """Load tool events from transcript for context, filtered by terminal.

    This is a placeholder that will fail all tests until implemented.
    """
    raise NotImplementedError("load_tool_events_for_context not yet implemented")


class TestLoadToolEventsTerminalScoping:
    """Tests for terminal-scoped evidence filtering in load_tool_events_for_context."""

    def test_two_terminals_same_session_return_only_own_events(self, tmp_path):
        """
        Test that two terminals in the same session only see their own tool events.

        Given: A transcript with tool events from two terminals
        When: load_tool_events_for_context is called for terminal_a
        Then: Only events from terminal_a are returned
        """
        # Create transcript with events from two terminals
        transcript_path = tmp_path / "transcript.jsonl"
        events = [
            {
                "type": "tool_use",
                "name": "Edit",
                "id": "tool_a_1",
                "terminal_id": "terminal_a",
                "input": {"file_path": "/path/to/file.py"},
            },
            {
                "type": "tool_use",
                "name": "Edit",
                "id": "tool_b_1",
                "terminal_id": "terminal_b",
                "input": {"file_path": "/path/to/other.py"},
            },
            {
                "type": "tool_use",
                "name": "Read",
                "id": "tool_a_2",
                "terminal_id": "terminal_a",
                "input": {"file_path": "/path/to/file.py"},
            },
        ]

        with open(transcript_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Call function for terminal_a
        result = load_tool_events_for_context(
            transcript_path=transcript_path,
            terminal_id="terminal_a",
            turn_start_event_id=0,
        )

        # Verify only terminal_a events are returned
        assert len(result) == 2
        assert all(event["terminal_id"] == "terminal_a" for event in result)
        assert result[0]["id"] == "tool_a_1"
        assert result[1]["id"] == "tool_a_2"

    def test_missing_terminal_id_returns_empty_list_fail_safe(self, tmp_path):
        """
        Test that missing terminal_id returns empty list (fail-safe behavior).

        Given: A transcript with tool events
        When: load_tool_events_for_context is called with terminal_id=None
        Then: Empty list is returned (no events loaded)
        """
        # Create transcript with events
        transcript_path = tmp_path / "transcript.jsonl"
        events = [
            {
                "type": "tool_use",
                "name": "Edit",
                "id": "tool_1",
                "terminal_id": "terminal_a",
                "input": {"file_path": "/path/to/file.py"},
            },
        ]

        with open(transcript_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Call function with terminal_id=None
        result = load_tool_events_for_context(
            transcript_path=transcript_path,
            terminal_id=None,
            turn_start_event_id=0,
        )

        # Verify empty list is returned (fail-safe)
        assert result == []

    def test_turn_start_event_id_filters_events(self, tmp_path):
        """
        Test that turn_start_event_id filters events to only those after the marker.

        Given: A transcript with tool events before and after turn marker
        When: load_tool_events_for_context is called with turn_start_event_id
        Then: Only events after the marker are returned
        """
        # Create transcript with events
        transcript_path = tmp_path / "transcript.jsonl"
        events = [
            {
                "type": "tool_use",
                "name": "Edit",
                "id": "tool_1",
                "terminal_id": "terminal_a",
                "event_id": 1,
            },
            {
                "type": "tool_use",
                "name": "Read",
                "id": "tool_2",
                "terminal_id": "terminal_a",
                "event_id": 5,  # After turn_start_event_id=3
            },
        ]

        with open(transcript_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Call function with turn_start_event_id=3
        result = load_tool_events_for_context(
            transcript_path=transcript_path,
            terminal_id="terminal_a",
            turn_start_event_id=3,
        )

        # Verify only events after event_id=3 are returned
        assert len(result) == 1
        assert result[0]["id"] == "tool_2"
        assert result[0]["event_id"] == 5
