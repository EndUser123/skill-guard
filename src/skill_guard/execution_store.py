"""
execution_store.py
==================

ExecutionStore interface + ArtifactsExecutionStore implementation.

Sole authority path: P:/.claude/.artifacts/console_{terminal_id}/execution-state.json
Append-only log: P:/.claude/.artifacts/console_{terminal_id}/execution-events.jsonl
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .execution_run import ExecutionEvent, ExecutionRun


class ExecutionStore(ABC):
    """Abstract store interface for execution runs."""

    @abstractmethod
    def load_active_run(self) -> ExecutionRun | None:
        """Load the active run for this terminal, if any."""
        ...

    @abstractmethod
    def save_run(self, run: ExecutionRun) -> None:
        """Atomically write run state to the store."""
        ...

    @abstractmethod
    def end_run(self, run: ExecutionRun, status: str) -> None:
        """End the run: append run_ended event, clear state."""
        ...

    @abstractmethod
    def append_event(self, event: ExecutionEvent) -> None:
        """Append an event to the append-only event log."""
        ...

    @abstractmethod
    def replay_events(self) -> list[ExecutionEvent]:
        """Replay all events from the event log."""
        ...

    @abstractmethod
    def console_dir(self) -> Path:
        """Return the console-specific artifact directory."""
        ...


class ArtifactsExecutionStore(ExecutionStore):
    """
    File-based execution store using .artifacts/console_{terminal_id}/.

    Layout:
      .artifacts/console_{terminal_id}/
        identity.json          (existing, not managed here)
        execution-state.json   (sole authority for active run)
        execution-events.jsonl (append-only event log)
    """

    ARTIFACTS_ROOT = Path("P:/.claude/.artifacts")

    def __init__(self, terminal_id: str):
        self._terminal_id = terminal_id

    def console_dir(self) -> Path:
        safe = self._terminal_id.replace("/", "-").replace("\\", "-").replace(":", "-")
        return self.ARTIFACTS_ROOT / f"console_{safe}"

    def _state_path(self) -> Path:
        return self.console_dir() / "execution-state.json"

    def _events_path(self) -> Path:
        return self.console_dir() / "execution-events.jsonl"

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Atomic write: temp-file-write + rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(path))

    def load_active_run(self) -> ExecutionRun | None:
        state_path = self._state_path()
        if not state_path.exists():
            return None
        try:
            d = json.loads(state_path.read_text(encoding="utf-8"))
            return ExecutionRun.from_jsonable(d)
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    def save_run(self, run: ExecutionRun) -> None:
        run.updated_at = __import__("time").time()
        self._atomic_write_json(self._state_path(), run.to_jsonable())

    def end_run(self, run: ExecutionRun, status: str) -> None:
        """Append run_ended event and delete state file (atomic rename to backup)."""
        event = ExecutionEvent(event_type="run_ended", status=status)
        self.append_event(event)

        state_path = self._state_path()
        if state_path.exists():
            # Rename to .ended backup (not deleted — for post-mortem)
            backup = state_path.with_suffix(".json.ended")
            if backup.exists():
                backup.unlink()
            state_path.rename(backup)

    def append_event(self, event: ExecutionEvent) -> None:
        events_path = self._events_path()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_jsonable(), ensure_ascii=False) + "\n"
        with events_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def replay_events(self) -> list[ExecutionEvent]:
        events_path = self._events_path()
        if not events_path.exists():
            return []
        events: list[ExecutionEvent] = []
        try:
            for line in events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    events.append(ExecutionEvent.from_jsonable(d))
                except (json.JSONDecodeError, KeyError):
                    continue
        except OSError:
            pass
        return events