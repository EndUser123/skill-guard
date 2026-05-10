r"""Pytest configuration for skill-guard test suite.

This module configures pytest fixtures and hooks used across all
skill-guard test modules, including database setup/teardown, temporary
directory management, and test isolation utilities.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure skill_guard src and skills packages are importable
hooks_path = str(Path(r"P:\\\\\\.claude/hooks").resolve())
skill_guard_root = str(Path(__file__).parent.parent.resolve())
for _p in (hooks_path, skill_guard_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Verify skills is importable (for migrate-skill-ct tests)
import os

os.makedirs(skill_guard_root, exist_ok=True)

# Import posttooluse (hooks version) and register skill_command_hook in sys.modules.
# _clear_shadowed_hook_packages() removes posttooluse from sys.modules during
# test_PreToolUse_skill_pattern_gate.py collection. By importing SkillCommandHook
# here and registering it, we survive the clearing.
import posttooluse  # noqa: F401
from posttooluse.skill_command_hook import SkillCommandHook

# Register the actual module (not the class) so "from posttooluse.skill_command_hook import X"
# works via normal Python import resolution. Storing just the class causes Python to
# interpret the import as "from SkillCommandHook import SkillCommandHook".
import posttooluse.skill_command_hook as skill_command_hook_module
sys.modules["posttooluse.skill_command_hook"] = skill_command_hook_module


def pytest_collection_modifyitems(items):
    """Re-register posttooluse.skill_command_hook after collection.

    _clear_shadowed_hook_packages() in PreToolUse_skill_pattern_gate.py clears
    posttooluse AND its submodules from sys.modules during test file collection.
    This runs AFTER collection (before fixtures), giving us a clean slate to
    re-register before any fixtures run.

    Must handle ModuleNotFoundError gracefully — if posttooluse itself can't
    be imported (e.g., missing optional dependencies in __init__.py), catch
    and skip rather than crashing the collection hook.
    r"""
    hooks_path_str = str(Path(r"P:\\\\\\.claude/hooks").resolve())
    # Ensure hooks path is at front (highest priority)
    if hooks_path_str in sys.path:
        sys.path.remove(hooks_path_str)
    sys.path.insert(0, hooks_path_str)

    # Ensure posttooluse package is importable
    if "posttooluse" not in sys.modules:
        try:
            import posttooluse  # noqa: F401
        except (ModuleNotFoundError, ImportError):
            pass  # posttooluse not available, skip registration

    # Register skill_command_hook submodule
    if "posttooluse.skill_command_hook" not in sys.modules:
        try:
            import posttooluse.skill_command_hook as skill_command_hook_module
            sys.modules["posttooluse.skill_command_hook"] = skill_command_hook_module
        except (ModuleNotFoundError, ImportError):
            pass  # submodule not available, skip registration

# Skills that tests use without real SKILL.md files
# This includes ALL test skill names used across all test files to ensure
# _load_workflow_steps returns dummy steps (not empty list) so that
# initialize_breadcrumb_trail creates actual trail files.
TEST_SKILL_NAMES = frozenset(
    {
        # test_breadcrumb.py
        "research",
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
        # test_breadcrumb_extended.py
        "test_skill",
        "test_workflow_skill",
    }
)

# Dummy workflow steps for test skills (no real SKILL.md needed)
# Default for generic test skills
DUMMY_WORKFLOW_STEPS = [
    {"id": "step1", "kind": "execution", "optional": False},
    {"id": "step2", "kind": "execution", "optional": False},
]

# Per-skill workflow steps for tests that need specific steps
DUMMY_WORKFLOW_STEPS_PER_SKILL = {
    # test_breadcrumb.py expects 7 steps for "research" skill
    "research": [
        {"id": "analyze_query_intent", "kind": "execution", "optional": False},
        {"id": "select_search_mode", "kind": "execution", "optional": False},
        {"id": "choose_providers", "kind": "execution", "optional": False},
        {"id": "execute_search", "kind": "execution", "optional": False},
        {"id": "synthesize_results", "kind": "execution", "optional": False},
        {"id": "fetch_urls", "kind": "execution", "optional": False},
        {"id": "format_output", "kind": "verification", "optional": False},
    ],
    "gto": [{"id": "execute_gto_analysis", "kind": "execution", "optional": False}],
    # test_breadcrumb_extended.py TestSetBreadcrumbEvidence
    "test_skill": [
        {"id": "step1", "kind": "execution", "optional": False},
        {"id": "step2", "kind": "verification", "optional": True},
    ],
    # test_breadcrumb_extended.py TestLoadWorkflowStepsStringFormat
    "test_workflow_skill": [
        {"id": "step_a", "kind": "execution", "optional": False},
        {"id": "step_b", "kind": "execution", "optional": False},
    ],
    # test_breadcrumb_isolation.py test_concurrent_terminals_dont_interfere
    "skill_terminal_a": [
        {"id": "step1", "kind": "execution", "optional": False},
        {"id": "step2", "kind": "execution", "optional": False},
    ],
    "skill_terminal_b": [
        {"id": "step1", "kind": "execution", "optional": False},
        {"id": "step2", "kind": "execution", "optional": False},
    ],
    # test_breadcrumb_isolation.py test_cleanup_stale_breadcrumbs_preserves_current_terminal
    "test_stale_cleanup": [
        {"id": "step1", "kind": "execution", "optional": False},
        {"id": "step2", "kind": "execution", "optional": False},
    ],
}


@pytest.fixture(autouse=True)
def mock_detect_terminal_id(request):
    r"""Mock detect_terminal_id to return a test-only terminal ID.

    Prevents pytest from touching real P:\\\\\\.claude/state/breadcrumbs_*/
    files when detect_terminal_id() returns the actual Claude Code terminal ID.

    CRITICAL: Must patch at the SOURCE module (terminal_detection), not at the
    import binding in tracker.py. Both tracker.py AND cache.py import from
    terminal_detection and create their own local bindings. Patching one binding
    does NOT affect the other, and patching the source is the only way to affect
    all importers simultaneously.

    Skips:
    - test_no_import_error_warnings: uses inspect.getsourcefile on real detect_terminal_id
    - test_breadcrumb_isolation tests: specifically test terminal ID differences
    r"""
    from skill_guard.utils import terminal_detection as td_module

    node_name = request.node.name
    # Skip tests that inspect the real detect_terminal_id or test terminal isolation
    if node_name in (
        "test_no_import_error_warnings",
        "test_different_terminals_create_separate_dirs",
        "test_breadcrumb_files_are_terminal_scoped",
        "test_terminal_scoped_paths",
    ):
        yield
        return

    with patch.object(td_module, "detect_terminal_id", return_value="pytest_isolated"):
        yield


@pytest.fixture(autouse=True)
def patch_workflow_steps_for_test_skills():
    r"""Patch _load_workflow_steps to return dummy steps for test skill names.

    This allows isolation tests to create breadcrumb trails without needing
    real SKILL.md files in P:\\\\\\.claude/skills/.
    """
    from skill_guard.breadcrumb import tracker

    original_load = tracker._load_workflow_steps

    def patched_load(skill_name: str):
        # skill_name may be uppercase or lowercase depending on caller
        # Check both cases for robustness
        from skill_guard.breadcrumb.tracker import WorkflowStepsResult

        skill_lower = skill_name.lower()
        if skill_lower in DUMMY_WORKFLOW_STEPS_PER_SKILL:
            return WorkflowStepsResult(steps=DUMMY_WORKFLOW_STEPS_PER_SKILL[skill_lower], parse_error=None)
        if skill_name in TEST_SKILL_NAMES or skill_lower in TEST_SKILL_NAMES:
            return WorkflowStepsResult(steps=DUMMY_WORKFLOW_STEPS, parse_error=None)
        return original_load(skill_name)

    with patch.object(tracker, "_load_workflow_steps", patched_load):
        yield


@pytest.fixture(autouse=True)
def clean_breadcrumb_state_and_logs():
    r"""Clean up breadcrumb state (.json) and log (.jsonl) files before each test.

    The AppendOnlyBreadcrumbLog stores entries in persistent files under
    P:\\\\\\.claude/state/. Without cleanup, entries accumulate across test runs.
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
    from skill_guard.breadcrumb.inference import _RUNTIME_MAPPINGS

    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()
    _RUNTIME_MAPPINGS.clear()

    yield

    tracker._cache._cache.clear()
    tracker._cache._access_times.clear()
    _RUNTIME_MAPPINGS.clear()
