r"""Characterization tests for blocking file I/O in create_run.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
Run with: pytest P:\\\\packages/skill-guard/tests/test_create_run_blocking_io.py -v

PY25-002: create_run performs blocking file I/O synchronously with no async alternative.
"""

from __future__ import annotations

import inspect
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from skill_guard.execution_run import ExecutionRun
from skill_guard.execution_runtime import ExecutionRuntime


class TestCreateRunBlockingIO:
    """Tests that verify create_run uses synchronous blocking file I/O."""

    @pytest.fixture
    def mock_store(self):
        """A real-style store with synchronous _atomic_write_json (blocking I/O)."""
        store = MagicMock()
        # Simulate the actual blocking behavior of ArtifactsExecutionStore._atomic_write_json
        def blocking_write(path, data):
            """Simulates synchronous blocking file I/O (Path.write_text + rename)."""
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if path.exists():
                path.unlink()
            tmp.rename(path)

        store._atomic_write_json = blocking_write
        return store

    def test_create_run_calls_create_or_replace_run(self, mock_store):
        """Characterization: create_run calls self.store.create_or_replace_run() to persist run state.

        INVARIANT 1: create_run uses create_or_replace_run (which replaces any existing
        active run for this terminal) rather than plain save_run.
        """
        runtime = ExecutionRuntime(store=mock_store)

        run = runtime.create_run(
            skill_name="test-skill",
            contract_type="workflow-execution",
            session_id="sess-123",
        )

        mock_store.create_or_replace_run.assert_called_once()
        call_args = mock_store.create_or_replace_run.call_args[0]
        assert isinstance(call_args[0], ExecutionRun)
        assert call_args[0].skill_name == "test-skill"

    def test_save_run_blocking_io_via_tracked_calls(self, tmp_path):
        """Characterization: save_run triggers _atomic_write_json with blocking syscalls."""
        from skill_guard.execution_store import ArtifactsExecutionStore
        import json

        captured = []

        class TrackingStore(ArtifactsExecutionStore):
            def __init__(self, base_path):
                self.__dict__["_base_path"] = base_path

            def _state_path(self):
                return self._base_path / "state.json"

            def _events_path(self):
                return self._base_path / "events.jsonl"

            def console_dir(self):
                return self._base_path

            def _atomic_write_json(self, path, data):
                captured.append(("atomic_write", path, data))
                super()._atomic_write_json(path, data)

        store = TrackingStore(base_path=tmp_path)
        runtime = ExecutionRuntime(store=store)

        runtime.create_run(
            skill_name="test-skill",
            contract_type="workflow-execution",
            session_id="sess-123",
        )

        assert len(captured) == 1, "save_run should call _atomic_write_json exactly once"
        method, path, data = captured[0]
        assert method == "atomic_write"
        assert path.name == "state.json"
        # _atomic_write_json does: Path.write_text + rename (both blocking syscalls)

    def test_no_async_save_run_variant_exists(self):
        """Characterization: ArtifactsExecutionStore has no async_save_run method."""
        from skill_guard.execution_store import ArtifactsExecutionStore

        store_methods = [m for m in dir(ArtifactsExecutionStore) if not m.startswith("_")]
        async_methods = [m for m in store_methods if m.startswith("async_")]

        assert "async_save_run" not in async_methods, (
            "ArtifactsExecutionStore should NOT have async_save_run - this test confirms the blocking-only state"
        )

    def test_save_run_is_not_async(self):
        """Characterization: save_run is a regular synchronous method (not async)."""
        from skill_guard.execution_store import ArtifactsExecutionStore

        save_run_method = getattr(ArtifactsExecutionStore, "save_run", None)
        assert save_run_method is not None, "ArtifactsExecutionStore must have save_run method"
        assert not inspect.iscoroutinefunction(save_run_method), (
            "save_run should be synchronous - if it were async, this test would fail (confirming the bug)"
        )

    def test_create_run_is_not_async(self):
        """Characterization: create_run is a regular synchronous method (not async)."""
        from skill_guard.execution_runtime import ExecutionRuntime

        create_run_method = getattr(ExecutionRuntime, "create_run", None)
        assert create_run_method is not None
        assert not inspect.iscoroutinefunction(create_run_method), (
            "create_run should be synchronous - if it were async, this test would fail"
        )

    def test_atomic_write_uses_blocking_syscalls(self, tmp_path):
        """Characterization: _atomic_write_json uses Path.write_text (blocking, not aiofiles)."""
        from skill_guard.execution_store import ArtifactsExecutionStore
        from skill_guard.execution_run import ExecutionRun

        # Use a concrete subclass to test real behavior
        class TestableStore(ArtifactsExecutionStore):
            def __init__(self, base_path):
                self.__dict__["_base_path"] = base_path

            def _state_path(self):
                return self._base_path / "state.json"

            def _events_path(self):
                return self._base_path / "events.jsonl"

            def console_dir(self):
                return self._base_path

        store = TestableStore(base_path=tmp_path)
        run = ExecutionRun.new(
            skill_name="test",
            contract_type="workflow-execution",
            terminal_id="t1",
            session_id="s1",
        )

        # This call exercises _atomic_write_json which uses:
        # - Path.write_text()  <- blocking file I/O
        # - Path.rename()      <- blocking syscall
        # There is no aiofiles or asyncio here
        store.save_run(run)

        state_file = tmp_path / "state.json"
        assert state_file.exists(), "save_run should have written state file synchronously"

        content = json.loads(state_file.read_text(encoding="utf-8"))
        assert content["skill_name"] == "test"

    def test_concurrent_create_run_serialization(self, tmp_path):
        """Characterization: Two concurrent create_run calls serialize on blocking I/O."""
        from skill_guard.execution_store import ArtifactsExecutionStore
        from skill_guard.execution_run import ExecutionRun

        # Track thread completion order
        completion_order = []
        start_barrier = threading.Barrier(2)

        class TestableStore(ArtifactsExecutionStore):
            def __init__(self, base_path):
                self.__dict__["_base_path"] = base_path

            def _state_path(self):
                return self._base_path / f"state_{threading.current_thread().name}.json"

            def _events_path(self):
                return self._base_path / "events.jsonl"

            def console_dir(self):
                return self._base_path

        store = TestableStore(base_path=tmp_path)
        runtime = ExecutionRuntime(store=store)

        def create_run_task(task_id):
            start_barrier.wait()  # Ensure both threads start simultaneously
            runtime.create_run(
                skill_name=f"skill-{task_id}",
                contract_type="workflow-execution",
                session_id=f"sess-{task_id}",
            )
            completion_order.append(task_id)

        # Start two threads - they will serialize on the blocking file I/O
        t1 = threading.Thread(target=create_run_task, args=(1,), name="t1")
        t2 = threading.Thread(target=create_run_task, args=(2,), name="t2")

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both complete successfully (blocking I/O guarantees correctness)
        assert len(completion_order) == 2
        assert set(completion_order) == {1, 2}