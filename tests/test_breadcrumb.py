#!/usr/bin/env python3
"""
Test suite for breadcrumb trail verification system.

Tests the skill_guard.breadcrumb module which provides workflow step
verification for skill execution.
"""

import json
import sys
import time
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skill_guard.breadcrumb import (
    cleanup_session_breadcrumbs,
    cleanup_stale_breadcrumbs,
    clear_breadcrumb_trail,
    format_breadcrumb_status,
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
    verify_breadcrumb_trail,
    verify_session_isolation,
)


@pytest.fixture
def cleanup_test_state():
    """Clean up breadcrumb state after each test."""
    yield
    # Clean up any breadcrumb trails created during test
    try:
        clear_breadcrumb_trail("research")
        clear_breadcrumb_trail("gto")
    except Exception:
        pass


def test_initialize_trail(cleanup_test_state):
    """Test breadcrumb trail initialization."""
    print("Test 1: Initialize breadcrumb trail")
    initialize_breadcrumb_trail("research")

    trail = get_breadcrumb_trail("research")
    assert trail is not None, "Trail should be created"
    assert trail["skill"] == "research", "Skill name should match"
    assert len(trail["workflow_steps"]) == 7, "Should have 7 workflow steps"
    assert len(trail["completed_steps"]) == 0, "No steps completed yet"
    assert "terminal_id" in trail, "Trail should have terminal_id"
    assert "session_id" not in trail, "Trail should NOT have session_id (changes during compaction)"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_set_breadcrumb(cleanup_test_state):
    """Test setting breadcrumb steps."""
    print("Test 2: Set breadcrumb steps")
    initialize_breadcrumb_trail("research")

    set_breadcrumb("research", "analyze_query_intent")
    set_breadcrumb("research", "select_search_mode")

    trail = get_breadcrumb_trail("research")
    assert len(trail["completed_steps"]) == 2, "Should have 2 completed steps"
    assert "analyze_query_intent" in trail["completed_steps"], "First step should be recorded"
    assert trail["current_step"] == "select_search_mode", "Current step should be last set"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_verify_complete_trail(cleanup_test_state):
    """Test verification of complete trail."""
    print("Test 3: Verify complete breadcrumb trail")
    initialize_breadcrumb_trail("research")

    # Complete all steps
    steps = [
        "analyze_query_intent",
        "select_search_mode",
        "choose_providers",
        "execute_search",
        "synthesize_results",
        "fetch_urls",
        "format_output",
    ]

    for step in steps:
        set_breadcrumb("research", step)

    is_complete, message = verify_breadcrumb_trail("research")
    assert is_complete, f"Trail should be complete: {message}"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_verify_incomplete_trail(cleanup_test_state):
    """Test verification of incomplete trail."""
    print("Test 4: Verify incomplete breadcrumb trail")
    initialize_breadcrumb_trail("research")

    # Complete only 3 of 7 steps
    set_breadcrumb("research", "analyze_query_intent")
    set_breadcrumb("research", "select_search_mode")
    set_breadcrumb("research", "choose_providers")

    is_complete, message = verify_breadcrumb_trail("research")
    assert not is_complete, "Trail should be incomplete"
    assert "Missing workflow steps" in message, "Should mention missing steps"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_invalid_step(cleanup_test_state):
    """Test setting invalid breadcrumb step."""
    print("Test 5: Set invalid breadcrumb step")
    initialize_breadcrumb_trail("research")

    # Try to set a step that's not in workflow_steps
    set_breadcrumb("research", "invalid_step_name")

    trail = get_breadcrumb_trail("research")
    assert len(trail["completed_steps"]) == 0, "Invalid step should not be recorded"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_no_workflow_steps(cleanup_test_state):
    """Test skill with no workflow_steps declared."""
    print("Test 6: Skill with no workflow_steps")
    initialize_breadcrumb_trail("gto")  # gto has no workflow_steps

    trail = get_breadcrumb_trail("gto")
    assert trail is None, "No trail should be created for skills without workflow_steps"

    print("  ✓ PASS\n")


def test_format_status(cleanup_test_state):
    """Test breadcrumb status formatting."""
    print("Test 7: Format breadcrumb status")
    initialize_breadcrumb_trail("research")

    set_breadcrumb("research", "analyze_query_intent")
    set_breadcrumb("research", "select_search_mode")

    trail = get_breadcrumb_trail("research")
    status = format_breadcrumb_status(trail)

    assert "Skill: research" in status, "Status should show skill name"
    assert "Workflow: 2/7" in status, "Status should show completion ratio"
    assert "Completed:" in status, "Status should show completed steps"
    assert "Missing:" in status, "Status should show missing steps"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_session_isolation(cleanup_test_state):
    """Test session isolation (multi-terminal safety)."""
    print("Test 8: Session isolation verification")
    initialize_breadcrumb_trail("research")

    trail = get_breadcrumb_trail("research")
    assert trail is not None, "Trail should be created"

    # Verify session isolation
    is_isolated = verify_session_isolation(trail)
    assert is_isolated, "Trail should be isolated to current session"

    clear_breadcrumb_trail("research")
    print("  ✓ PASS\n")


def test_cleanup_session_breadcrumbs(cleanup_test_state):
    """Test cleanup on session end."""
    print("Test 9: Session cleanup")
    initialize_breadcrumb_trail("research")
    initialize_breadcrumb_trail("gto")  # gto has no workflow_steps, won't create trail

    # Verify trails exist
    research_trail = get_breadcrumb_trail("research")
    assert research_trail is not None, "Research trail should exist"

    # Clean up session
    cleaned_count = cleanup_session_breadcrumbs()
    assert cleaned_count >= 1, "Should clean up at least 1 trail"

    # Verify trails are gone
    research_trail = get_breadcrumb_trail("research")
    assert research_trail is None, "Research trail should be cleaned up"

    print("  ✓ PASS\n")


def test_cleanup_stale_breadcrumbs(cleanup_test_state):
    """Test cleanup of stale breadcrumbs."""
    print("Test 10: Stale breadcrumb cleanup")
    initialize_breadcrumb_trail("research")

    # Manually age the trail by modifying initialized_at
    trail = get_breadcrumb_trail("research")
    if trail:
        from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

        trail_file = _get_breadcrumb_file("research")
        if trail_file.exists():
            trail_data = json.loads(trail_file.read_text())
            # Set initialized_at to 3 hours ago (stale)
            trail_data["initialized_at"] = time.time() - (3 * 3600)
            trail_file.write_text(json.dumps(trail_data, indent=2))

    # Clean up stale trails
    cleaned_count = cleanup_stale_breadcrumbs()
    assert cleaned_count >= 1, "Should clean up at least 1 stale trail"

    # Verify trail is gone
    research_trail = get_breadcrumb_trail("research")
    assert research_trail is None, "Stale trail should be cleaned up"

    print("  ✓ PASS\n")


def run_all_tests():
    """Run all tests without pytest."""
    print("=" * 60)
    print("BREADCRUMB VERIFIER TEST SUITE v2.0")
    print("Testing multi-terminal safety and cleanup protocol")
    print("=" * 60)
    print()

    tests = [
        test_initialize_trail,
        test_set_breadcrumb,
        test_verify_complete_trail,
        test_verify_incomplete_trail,
        test_invalid_step,
        test_no_workflow_steps,
        test_format_status,
        test_session_isolation,
        test_cleanup_session_breadcrumbs,
        test_cleanup_stale_breadcrumbs,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
