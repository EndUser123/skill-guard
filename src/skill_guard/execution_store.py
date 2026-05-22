r"""
execution_store.py
==================

ExecutionStore interface + ArtifactsExecutionStore implementation.

Sole authority path: P:\\\\\\.claude/.artifacts/console_{terminal_id}/execution-state.json
Append-only log: P:\\\\\\.claude/.artifacts/console_{terminal_id}/execution-events.jsonl

INVARIANT 1 (one active run per terminal):
  execution-state.json is the SOLE authority for active contract runs.
  At most one ACTIVE run exists per terminal_id at any time.
  When a new run is created for a terminal with an existing ACTIVE run,
  the prior run is silently ended and replaced — the new run takes ownership.
  This prevents contract fragmentation across multiple simultaneous runs.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .execution_run import ExecutionEvent, ExecutionRun


class ExecutionStore(ABC):
    r"""Abstract store interface for execution runs."""

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

    @abstractmethod
    def create_or_replace_run(self, run: ExecutionRun) -> None:
        """
        Atomically create or replace the active run for this terminal.

        INVARIANT 1 (one active run per terminal):
          If a run already exists for this terminal, it is silently ended
          (run_ended emitted with status=replaced) and the new run takes over.
          Only one ACTIVE run exists per terminal at any time.
        """
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

    ARTIFACTS_ROOT = Path(r"P:\\\\\\.claude/.artifacts")

    def __init__(self, terminal_id: str):
        self._terminal_id = terminal_id

    def console_dir(self) -> Path:
        safe = self._terminal_id.replace("/", "-").replace("\\", "-").replace(":", "-")
        # Avoid double-prefix when terminal_id already has console_ prefix
        if safe.startswith("console_"):
            return self.ARTIFACTS_ROOT / safe
        return self.ARTIFACTS_ROOT / f"console_{safe}"

    def _state_path(self) -> Path:
        return self.console_dir() / "execution-state.json"

    def _events_path(self) -> Path:
        return self.console_dir() / "execution-events.jsonl"

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Atomic write: temp-file-write + rename.

        Retries once with gc.collect() on WinError 32 (PermissionError).
        Raises on repeated failure — callers must handle.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        text = json.dumps(data, indent=2, ensure_ascii=False)
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(str(tmp), str(path))
        except PermissionError:
            import gc
            gc.collect()
            try:
                tmp.write_text(text, encoding="utf-8")
                os.replace(str(tmp), str(path))
            except PermissionError:
                raise OSError(f"Failed to write {path} after retry") from None

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

    def create_or_replace_run(self, run: ExecutionRun) -> None:
        prev = self.load_active_run()
        if prev is not None:
            self.end_run(prev, "replaced")
        self.save_run(run)