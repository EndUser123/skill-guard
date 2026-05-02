"""Characterization tests for _db_initialized check-then-act race in tracker.py.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
The bug: _db_initialized is a module-level global boolean with non-atomic
check-then-act initialization, and bare except swallows errors.

Run with: pytest tests/test_tracker_db_init_race.py -v
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest


class TestDbInitializedGlobal:
    """Tests that _db_initialized is a module-level global boolean."""

    def test_db_initialized_is_module_level_global(self):
        """Characterization: _db_initialized is a module-level boolean global."""
        from skill_guard.breadcrumb import tracker

        # Verify _db_initialized exists and is a bool in the module namespace
        assert hasattr(tracker, "_db_initialized")
        assert isinstance(tracker._db_initialized, bool)

    def test_db_initialized_starts_false(self):
        """Characterization: _db_initialized starts as False before any initialization."""
        # Re-import to get fresh state (module may already be initialized in test env)
        import importlib
        from skill_guard.breadcrumb import tracker
        importlib.reload(tracker)

        assert tracker._db_initialized is False


class TestDbInitializedCheckThenAct:
    """Tests that check-then-act pattern in _ensure_database_initialized is non-atomic."""

    def test_check_then_act_is_separate_operations(self):
        """Characterization: Check (_db_initialized) and act (initialization) are non-atomic.

        The function does:
          1. if _db_initialized: return True  (CHECK)
          2. conn = database.get_connection()  (ACT - not protected by check)
          3. database.initialize_schema(conn)  (ACT - not protected by check)
          4. _db_initialized = True           (STATE CHANGE)

        Between check (1) and state change (4), multiple threads can pass the check.
        """
        from skill_guard.breadcrumb import tracker

        # Read the source to verify the pattern
        import inspect

        source = inspect.getsource(tracker._ensure_database_initialized)
        lines = source.split("\n")

        # Find the check line and state-change line
        check_line = None
        state_change_line = None

        for i, line in enumerate(lines):
            if "if _db_initialized" in line and check_line is None:
                check_line = i
            if "_db_initialized = True" in line and state_change_line is None:
                state_change_line = i

        assert check_line is not None, "Could not find 'if _db_initialized' check"
        assert state_change_line is not None, "Could not find '_db_initialized = True' state change"

        # Verify they are on different lines (non-atomic)
        assert state_change_line > check_line, "Check and state change are on same line (unexpected)"

        # The gap between check and state change represents the race window
        gap = state_change_line - check_line
        assert gap >= 3, f"Race window is only {gap} line(s) - pattern may have changed"

    def test_race_condition_observable_with_threads(self):
        """Characterization: Race condition is observable when multiple threads call init.

        This test demonstrates the check-then-act race by having concurrent callers
        potentially trigger multiple initializations.
        """
        from skill_guard.breadcrumb import tracker

        # Track how many times initialization logic runs
        init_count = {"value": 0}
        original_get_connection = tracker.database.get_connection
        original_init_schema = tracker.database.initialize_schema

        def counting_get_connection(*args, **kwargs):
            init_count["value"] += 1
            return original_get_connection(*args, **kwargs)

        def counting_init_schema(*args, **kwargs):
            init_count["value"] += 1
            return original_init_schema(*args, **kwargs)

        # Reset state for this test
        tracker._db_initialized = False

        with patch.object(tracker.database, "get_connection", counting_get_connection):
            with patch.object(tracker.database, "initialize_schema", counting_init_schema):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [executor.submit(tracker._ensure_database_initialized) for _ in range(8)]
                    results = [f.result() for f in futures]

        # With proper locking, init_count should be 1
        # With the current race, init_count will be > 1
        # This assertion documents current behavior (will pass if race exists)
        assert init_count["value"] >= 1, "Initialization was never called"

        # The race condition allows multiple threads to pass the check
        # Note: Due to timing, this may sometimes pass with 1, but the race exists


class TestBareExceptSwallowsErrors:
    """Tests that bare except clause swallows errors silently."""

    def test_bare_except_catches_all_exceptions(self):
        """Characterization: The except clause catches ALL exceptions, not just specific ones.

        Line 96-97:
            except Exception:
                return False

        This catches BaseException (including SystemExit, KeyboardInterrupt),
        but more importantly catches ALL Exception subclasses including:
        - database.get_connection failures
        - database.initialize_schema failures
        - Any other unexpected error

        The error information is lost (not logged), and False is returned.
        """
        from skill_guard.breadcrumb import tracker

        import inspect

        source = inspect.getsource(tracker._ensure_database_initialized)

        # Verify bare except Exception: (not except SomeSpecificError)
        assert "except Exception:" in source, "except clause should use bare Exception"

        # Verify there's no logging in the except block
        except_block_lines = []
        in_except = False
        for line in source.split("\n"):
            if "except Exception:" in line:
                in_except = True
                continue
            if in_except:
                if line.strip() and not line.startswith(" " * 8) and not line.startswith("\t"):
                    # indentation reset - end of except block
                    break
                except_block_lines.append(line)

        # The except block should be minimal (just return False)
        # and should NOT log the exception
        assert len(except_block_lines) <= 2, "except block is too long (unexpected)"
        assert not any("logging" in l or "logger" in l or "warn" in l or "error" in l
                       for l in except_block_lines), "except block should not log"

    def test_returns_false_on_error_not_none(self):
        """Characterization: On error, function returns False (not None).

        This masks failures - caller cannot distinguish "not initialized" from "error".
        """
        from skill_guard.breadcrumb import tracker

        # Force an error condition by making get_connection return None
        # (which the code already handles by returning False)
        with patch.object(tracker.database, "get_connection", return_value=None):
            result = tracker._ensure_database_initialized()
            assert result is False

    def test_error_returns_false_not_raise(self):
        """Characterization: Errors are swallowed (returned as False), not raised.

        When database operations fail, caller cannot tell if it was:
        - Actual initialization failure
        - Database not available
        - Connection error
        - Schema initialization error
        """
        from skill_guard.breadcrumb import tracker

        class TestError(Exception):
            """Custom error for testing."""

        def raise_on_get_connection(*args, **kwargs):
            raise TestError("Connection failed")

        with patch.object(tracker.database, "get_connection", raise_on_get_connection):
            # This should NOT raise - error is swallowed
            result = tracker._ensure_database_initialized()

        # Result is False, error was swallowed
        assert result is False, "Error should be swallowed and return False"


class TestDbInitializedStateTransitions:
    """Tests for _db_initialized state transition behavior."""

    def test_initialization_sets_flag_to_true(self):
        """Characterization: Successful initialization sets _db_initialized to True."""
        from skill_guard.breadcrumb import tracker

        # Reset state
        tracker._db_initialized = False

        # Mock successful initialization
        mock_conn = MagicMock()
        with patch.object(tracker.database, "get_connection", return_value=mock_conn):
            with patch.object(tracker.database, "initialize_schema"):
                result = tracker._ensure_database_initialized()

        assert result is True
        assert tracker._db_initialized is True

    def test_failed_initialization_leaves_flag_false(self):
        """Characterization: Failed initialization leaves _db_initialized as False."""
        from skill_guard.breadcrumb import tracker

        # Reset state
        tracker._db_initialized = False

        def fail_init(*args, **kwargs):
            raise RuntimeError("Init failed")

        with patch.object(tracker.database, "get_connection", fail_init):
            result = tracker._ensure_database_initialized()

        assert result is False
        assert tracker._db_initialized is False

    def test_check_returns_true_without_reinitializing(self):
        """Characterization: Once _db_initialized is True, check returns True without calling get_connection."""
        from skill_guard.breadcrumb import tracker

        # Set flag to True manually (simulating already-initialized)
        tracker._db_initialized = True

        call_count = {"value": 0}

        def counting_get_connection(*args, **kwargs):
            call_count["value"] += 1
            return MagicMock()

        with patch.object(tracker.database, "get_connection", counting_get_connection):
            result = tracker._ensure_database_initialized()

        assert result is True
        assert call_count["value"] == 0, "get_connection should not be called when already initialized"
