"""Pytest configuration for skill-guard test suite.

This module configures pytest fixtures and hooks used across all
skill-guard test modules, including database setup/teardown, temporary
directory management, and test isolation utilities.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Skills that tests use without real SKILL.md files
# This includes ALL test skill names used across all test files to ensure
# _load_workflow_steps returns dummy steps (not empty list) so that
# initialize_breadcrumb_trail creates actual trail files.
TEST_SKILL_NAMES = frozenset(
    {
        # Isolation tests
        "test_isolation_check",
        "test_wrong_terminal",
        "test_terminal_scoped",
        "test_clear_isolation",
        "test_cleanup_current_only",
        "skill_terminal_a",
        "skill_terminal_b",
        # Log tests
        "test_append_log",
        "test_multi_log",
        "test_chronological",
        "test_nonexistent_log",
        "test_malformed_log",
        "test_metadata",
        "test_clear_log",
        "test_clear_nonexistent",
        # Concurrent/log rotation tests
        "test_concurrent_a",
        "test_concurrent_b",
        "test_clear_cleanup",
        "test_stale_cleanup",
        # Log rotation tests
        "test_rotation_size",
        "test_rotation_timestamp",
        "test_rotation_replay",
        "test_rotation_multiple",
        "test_rotation_integrity",
        "test_rotation_concurrent",
        # Tiered verification tests
        "test_minimal_pass",
        "test_minimal_duration",
        "test_standard_pass",
        "test_strict_pass",
        "test_strict_fail",
        # T002/T005 integration tests
        "test_integration",
        "test_mark_complete",
        "test_verify",
        "test_e2e",
        "test_clear",
    }
)

# Dummy workflow steps for test skills (no real SKILL.md needed)
DUMMY_WORKFLOW_STEPS = [
    {"id": "step1", "kind": "execution", "optional": False},
    {"id": "step2", "kind": "execution", "optional": False},
    {"id": "test_step", "kind": "execution", "optional": False},
    {"id": "step_1", "kind": "execution", "optional": False},
    {"id": "step_2", "kind": "execution", "optional": False},
    {"id": "verify", "kind": "verification", "optional": False},
]


@pytest.fixture(autouse=True)
def mock_detect_terminal_id(request):
    """Mock detect_terminal_id to return a test-only terminal ID.

    Prevents pytest from touching real P:/.claude/state/breadcrumbs_*/
    files when detect_terminal_id() returns the actual Claude Code terminal ID.

    Patches at the correct namespace: skill_guard.breadcrumb.tracker.detect_terminal_id
    (tracker.py uses 'from skill_guard.utils.terminal_detection import detect_terminal_id',
    creating a local binding — patching the source module does NOT affect this local binding).

    Skips:
    - test_no_import_error_warnings: uses inspect.getsourcefile on real detect_terminal_id
    - test_breadcrumb_isolation tests: specifically test terminal ID differences
    """
    import skill_guard.breadcrumb.tracker as tracker_module

    node_name = request.node.name
    # Skip tests that inspect the real detect_terminal_id or test terminal isolation
    if node_name in (
        "test_no_import_error_warnings",
        "test_different_terminals_create_separate_dirs",
        "test_breadcrumb_files_are_terminal_scoped",
    ):
        yield
        return

    with patch.object(tracker_module, "detect_terminal_id", return_value="pytest_isolated"):
        yield


@pytest.fixture(autouse=True)
def patch_workflow_steps_for_test_skills():
    """Patch _load_workflow_steps to return dummy steps for test skill names.

    This allows isolation tests to create breadcrumb trails without needing
    real SKILL.md files in P:/.claude/skills/.
    """
    from skill_guard.breadcrumb import tracker

    original_load = tracker._load_workflow_steps

    def patched_load(skill_name: str):
        # skill_name may be uppercase or lowercase depending on caller
        # Check both cases for robustness
        if skill_name in TEST_SKILL_NAMES or skill_name.lower() in TEST_SKILL_NAMES:
            return DUMMY_WORKFLOW_STEPS
        return original_load(skill_name)

    with patch.object(tracker, "_load_workflow_steps", patched_load):
        yield


@pytest.fixture(autouse=True)
def clean_breadcrumb_state_and_logs():
    """Clean up breadcrumb state (.json) and log (.jsonl) files before each test.

    The AppendOnlyBreadcrumbLog stores entries in persistent files under
    P:/.claude/state/. Without cleanup, entries accumulate across test runs.
    Cleans ALL breadcrumb files (not just TEST_SKILL_NAMES) since any
    test could create entries for any skill name.

    Uses gc.collect() + rename workaround to handle Windows file handle caching.
    """
    import gc

    from skill_guard.breadcrumb.log import _get_log_dir
    from skill_guard.breadcrumb.tracker import _get_breadcrumb_dir

    log_dir = _get_log_dir()
    breadcrumb_dir = _get_breadcrumb_dir()

    def do_cleanup():
        """Clean all breadcrumb files, with robust Windows handle release."""
        import time as time_module

        # Force garbage collection to ensure file handles are released
        gc.collect()

        # Clean both the .jsonl log directory AND the .json breadcrumb directory
        # NOTE: Log files are {skill}.jsonl (e.g., code.jsonl), NOTbreadcrumb_*.jsonl (log.py:77)
        for dir_path in (log_dir, breadcrumb_dir):
            if dir_path.exists():
                for log_file in list(dir_path.glob("*.jsonl")) + list(
                    dir_path.glob("breadcrumb_*.json")
                ):
                    try:
                        log_file.unlink(missing_ok=True)
                    except OSError:
                        # On Windows, files may remain locked. Try a brief sleep and retry.
                        time_module.sleep(0.05)
                        try:
                            log_file.unlink(missing_ok=True)
                        except OSError:
                            # Final fallback: rename to a unique path (OS will clean eventually)
                            tmp_name = str(log_file) + f".orphaned_{time_module.time_ns()}"
                            try:
                                log_file.rename(tmp_name)
                            except OSError:
                                pass

    do_cleanup()

    yield

    do_cleanup()


@pytest.fixture(autouse=True)
def clear_breadcrumb_cache():
    """Clear the breadcrumb state cache between tests.

    The _cache module-level global can retain stale state between tests.
    """
    from skill_guard.breadcrumb import tracker

    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()

    yield

    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()
