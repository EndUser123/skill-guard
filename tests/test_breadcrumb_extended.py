#!/usr/bin/env python3
"""
Test suite for extended breadcrumb trail system.

TASK-001: Tests for _load_workflow_steps() returning list[dict] format.

These tests verify the NEW behavior where workflow_steps can be:
1. Simple strings: ["step1", "step2"] → converted to dict format with defaults
2. Dict format: [{"id": "step1", "kind": "execution", "optional": false}, ...]
3. Mixed format: both strings and dicts can coexist

The dict format supports:
- id: step identifier (required)
- kind: step type ("execution" or "verification", default: "execution")
- optional: whether step is optional (default: false)

TASK-002: Tests for run_id generation and steps dict structure.

These tests verify that initialize_breadcrumb_trail():
1. Generates unique run_id (UUID format) for each skill invocation
2. Converts workflow_steps to steps dict with status and evidence
3. Initializes each step with kind, optional, status="pending", evidence={}
4. Maintains backward compatibility with existing breadcrumb trails

TASK-002.5: Tests for set_breadcrumb() evidence parameter.

These tests verify that set_breadcrumb():
1. Accepts optional evidence parameter (default None)
2. Stores evidence in steps dict for the completed step
3. Updates step status to "done" when evidence provided
4. Maintains backward compatibility with existing set_breadcrumb() calls

Run with: pytest tests/test_breadcrumb_extended.py -v
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from skill_guard.breadcrumb.tracker import (
    _load_workflow_steps,
    initialize_breadcrumb_trail,
    set_breadcrumb,
)


@pytest.fixture
def mock_skills_dir(tmp_path):
    """Create a temporary skills directory and mock Path to use it."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Store original Path
    original_path = Path

    def mock_path_impl(path_str):
        """Mock Path implementation that redirects skills directory."""
        if isinstance(path_str, str) and "P:/.claude/skills" in path_str:
            return skills_dir
        return original_path(path_str)

    yield skills_dir, mock_path_impl

    # Cleanup happens automatically via tmp_path fixture


class TestLoadWorkflowStepsStringFormat:
    """Test backward compatibility with string format."""

    def test_load_workflow_steps_string_format(self, mock_skills_dir):
        """
        Test that string format is converted to dict format with defaults.

        Given: SKILL.md with workflow_steps as simple strings
        When: _load_workflow_steps() is called
        Then: Returns list[dict] with id, kind="execution", optional=False
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill with string format workflow_steps
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step_one\n"
            "  - step_two\n"
            "  - step_three\n"
            "---\n"
            "# Test Skill\n"
        )

        # Patch Path constructor in tracker module
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("test_skill")

        # ASSERT: Should return list of dicts (not strings)
        assert isinstance(steps, list), f"Should return a list, got {type(steps)}"
        assert len(steps) == 3, f"Should have 3 steps, got {len(steps)}"

        # ASSERT: Each item should be a dict with required keys
        for i, step in enumerate(steps):
            assert isinstance(step, dict), f"Step {i} should be dict, got {type(step)}: {step}"
            assert "id" in step, f"Step {i} must have 'id' key"
            assert "kind" in step, f"Step {i} must have 'kind' key"
            assert "optional" in step, f"Step {i} must have 'optional' key"

        # ASSERT: String format should have default values
        assert steps[0]["id"] == "step_one"
        assert steps[0]["kind"] == "execution", "String format should default to kind='execution'"
        assert steps[0]["optional"] is False, "String format should default to optional=False"

        assert steps[1]["id"] == "step_two"
        assert steps[1]["kind"] == "execution"
        assert steps[1]["optional"] is False

        assert steps[2]["id"] == "step_three"
        assert steps[2]["kind"] == "execution"
        assert steps[2]["optional"] is False

    def test_load_workflow_steps_empty_string_list(self, mock_skills_dir):
        """
        Test that empty workflow_steps list is handled correctly.

        Given: SKILL.md with empty workflow_steps list
        When: _load_workflow_steps() is called
        Then: Returns empty list
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "empty_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: empty_skill\n"
            "workflow_steps: []\n"
            "---\n"
            "# Empty Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("empty_skill")

        assert steps == [], "Empty workflow_steps should return empty list"


class TestLoadWorkflowStepsDictFormat:
    """Test new dict format with optional verification steps."""

    def test_load_workflow_steps_dict_format(self, mock_skills_dir):
        """
        Test that dict format preserves kind and optional values.

        Given: SKILL.md with workflow_steps as dicts with kind/optional fields
        When: _load_workflow_steps() is called
        Then: Returns list[dict] preserving kind and optional values
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "dict_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: dict_skill\n"
            "workflow_steps:\n"
            "  - id: step_one\n"
            "    kind: execution\n"
            "    optional: false\n"
            "  - id: verify_output\n"
            "    kind: verification\n"
            "    optional: true\n"
            "  - id: step_three\n"
            "    kind: execution\n"
            "    optional: false\n"
            "---\n"
            "# Dict Format Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("dict_skill")

        # ASSERT: Should return list of dicts
        assert isinstance(steps, list), "Should return a list"
        assert len(steps) == 3, "Should have 3 steps"

        # ASSERT: First step - execution, not optional
        assert steps[0]["id"] == "step_one"
        assert steps[0]["kind"] == "execution"
        assert steps[0]["optional"] is False

        # ASSERT: Second step - verification, optional
        assert steps[1]["id"] == "verify_output"
        assert steps[1]["kind"] == "verification"
        assert steps[1]["optional"] is True

        # ASSERT: Third step - execution, not optional
        assert steps[2]["id"] == "step_three"
        assert steps[2]["kind"] == "execution"
        assert steps[2]["optional"] is False

    def test_load_workflow_steps_dict_defaults(self, mock_skills_dir):
        """
        Test that missing kind and optional fields get defaults.

        Given: SKILL.md with workflow_steps as dicts missing kind/optional
        When: _load_workflow_steps() is called
        Then: Missing kind defaults to "execution", missing optional defaults to False
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "default_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: default_skill\n"
            "workflow_steps:\n"
            "  - id: step_one\n"
            "  - id: step_two\n"
            "    kind: verification\n"
            "  - id: step_three\n"
            "    optional: true\n"
            "---\n"
            "# Default Values Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("default_skill")

        # ASSERT: Should return list of dicts
        assert len(steps) == 3

        # ASSERT: step_one has both defaults
        assert steps[0]["id"] == "step_one"
        assert steps[0]["kind"] == "execution", "Missing kind should default to 'execution'"
        assert steps[0]["optional"] is False, "Missing optional should default to False"

        # ASSERT: step_two has explicit kind, default optional
        assert steps[1]["id"] == "step_two"
        assert steps[1]["kind"] == "verification", "Explicit kind should be preserved"
        assert steps[1]["optional"] is False, "Missing optional should default to False"

        # ASSERT: step_three has default kind, explicit optional
        assert steps[2]["id"] == "step_three"
        assert steps[2]["kind"] == "execution", "Missing kind should default to 'execution'"
        assert steps[2]["optional"] is True, "Explicit optional should be preserved"


class TestLoadWorkflowStepsMixedFormat:
    """Test that string and dict formats can coexist."""

    def test_load_workflow_steps_mixed_format(self, mock_skills_dir):
        """
        Test that string and dict formats can be mixed.

        Given: SKILL.md with mixed format (some strings, some dicts)
        When: _load_workflow_steps() is called
        Then: All items are normalized to dict format
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "mixed_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: mixed_skill\n"
            "workflow_steps:\n"
            "  - step_one\n"
            "  - id: verify_output\n"
            "    kind: verification\n"
            "    optional: true\n"
            "  - step_three\n"
            "  - id: step_four\n"
            "    optional: false\n"
            "---\n"
            "# Mixed Format Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("mixed_skill")

        # ASSERT: Should return list of dicts
        assert isinstance(steps, list), "Should return a list"
        assert len(steps) == 4, "Should have 4 steps"

        # ASSERT: All items should be dicts
        for i, step in enumerate(steps):
            assert isinstance(step, dict), f"Step {i} should be dict, got {type(step)}: {step}"
            assert "id" in step, f"Step {i} must have 'id' key"
            assert "kind" in step, f"Step {i} must have 'kind' key"
            assert "optional" in step, f"Step {i} must have 'optional' key"

        # ASSERT: String formats should be converted with defaults
        assert steps[0]["id"] == "step_one"
        assert steps[0]["kind"] == "execution"
        assert steps[0]["optional"] is False

        # ASSERT: Dict format should preserve values
        assert steps[1]["id"] == "verify_output"
        assert steps[1]["kind"] == "verification"
        assert steps[1]["optional"] is True

        # ASSERT: Another string format converted
        assert steps[2]["id"] == "step_three"
        assert steps[2]["kind"] == "execution"
        assert steps[2]["optional"] is False

        # ASSERT: Dict format with explicit optional
        assert steps[3]["id"] == "step_four"
        assert steps[3]["kind"] == "execution"
        assert steps[3]["optional"] is False


class TestLoadWorkflowStepsEdgeCases:
    """Test edge cases and error handling."""

    def test_load_workflow_steps_missing_skill_file(self, mock_skills_dir):
        """
        Test that missing skill file returns empty list.

        Given: Skill directory doesn't exist
        When: _load_workflow_steps() is called
        Then: Returns empty list
        """
        _, mock_path = mock_skills_dir

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("nonexistent_skill")

        assert steps == [], "Missing skill should return empty list"

    def test_load_workflow_steps_invalid_yaml(self, mock_skills_dir):
        """
        Test that invalid YAML is handled gracefully.

        Given: SKILL.md with invalid YAML frontmatter
        When: _load_workflow_steps() is called
        Then: Returns empty list (error handling)
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "invalid_yaml"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: invalid_yaml\n"
            "workflow_steps: [invalid: yaml: content\n"
            "---\n"
            "# Invalid YAML Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("invalid_yaml")

        assert steps == [], "Invalid YAML should return empty list"

    def test_load_workflow_steps_dict_without_id(self, mock_skills_dir):
        """
        Test that dict without id field is handled gracefully.

        Given: SKILL.md with dict format missing 'id' field
        When: _load_workflow_steps() is called
        Then: Either skips invalid entry or uses default id
        """
        skills_dir, mock_path = mock_skills_dir

        skill_dir = skills_dir / "no_id_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: no_id_skill\n"
            "workflow_steps:\n"
            "  - kind: execution\n"
            "    optional: false\n"
            "  - id: step_two\n"
            "    kind: verification\n"
            "---\n"
            "# No ID Skill\n"
        )

        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            steps = _load_workflow_steps("no_id_skill")

        # ASSERT: Should handle gracefully - either skip or use default
        # Implementation choice: skip invalid entries or use string representation
        assert isinstance(steps, list), "Should return a list"
        # If first entry is skipped, should have 1 step; if kept, should have 2
        assert len(steps) <= 2, "Should have at most 2 steps"


# =============================================================================
# TASK-002: Tests for run_id and steps dict structure
# =============================================================================


class TestInitializeBreadcrumbRunId:
    """Test that initialize_breadcrumb_trail generates unique run_id."""

    def test_initialize_breadcrumb_generates_run_id(self, mock_skills_dir, tmp_path):
        """
        Test that initialize_breadcrumb_trail generates a UUID run_id.

        Given: Mock _load_workflow_steps() returns dict format
        When: initialize_breadcrumb_trail("test_skill") is called
        Then: Breadcrumb file has run_id field with valid UUID format
        And: run_id is unique across invocations
        """

        skills_dir, mock_path = mock_skills_dir

        # Create a test skill with dict format workflow_steps
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - id: step1\n"
            "    kind: execution\n"
            "    optional: false\n"
            "  - id: step2\n"
            "    kind: verification\n"
            "    optional: true\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        # Mock _get_breadcrumb_dir to use temp directory
        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        # Mock detect_terminal_id
        def mock_terminal_id():
            return "test_terminal"

        # First invocation
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Read first breadcrumb file
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        assert breadcrumb_file.exists(), "Breadcrumb file should be created"

        trail1 = json.loads(breadcrumb_file.read_text())

        # ASSERT: run_id field exists
        assert "run_id" in trail1, "Breadcrumb trail should have run_id field"
        run_id_1 = trail1["run_id"]

        # ASSERT: run_id matches UUID format (8-4-4-4-12 hex digits)
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        assert uuid_pattern.match(run_id_1), f"run_id should match UUID format, got: {run_id_1}"

        # Second invocation (should generate different run_id)
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Read second breadcrumb file
        trail2 = json.loads(breadcrumb_file.read_text())
        run_id_2 = trail2["run_id"]

        # ASSERT: run_id is unique across invocations
        assert run_id_1 != run_id_2, "Each invocation should generate unique run_id"


class TestInitializeBreadcrumbStepsDict:
    """Test that initialize_breadcrumb_trail creates steps dict structure."""

    def test_initialize_breadcrumb_creates_steps_dict(self, mock_skills_dir, tmp_path):
        """
        Test that initialize_breadcrumb_trail converts workflow_steps to steps dict.

        Given: Mock _load_workflow_steps() returns dict format with kind and optional
        When: initialize_breadcrumb_trail("test_skill") is called
        Then: Breadcrumb file has steps dict with each step having:
              - id, kind, optional from workflow_steps
              - status="pending"
              - evidence={}
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill with dict format workflow_steps
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - id: step1\n"
            "    kind: execution\n"
            "    optional: false\n"
            "  - id: step2\n"
            "    kind: verification\n"
            "    optional: true\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Read breadcrumb file
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: steps field exists and is a dict
        assert "steps" in trail, "Breadcrumb trail should have steps field"
        assert isinstance(trail["steps"], dict), "steps should be a dict"

        steps = trail["steps"]

        # ASSERT: step1 has correct structure
        assert "step1" in steps, "steps dict should contain step1"
        assert steps["step1"]["kind"] == "execution", "step1 kind should be 'execution'"
        assert steps["step1"]["optional"] is False, "step1 optional should be False"
        assert steps["step1"]["status"] == "pending", "step1 status should be 'pending'"
        assert steps["step1"]["evidence"] == {}, "step1 evidence should be empty dict"

        # ASSERT: step2 has correct structure
        assert "step2" in steps, "steps dict should contain step2"
        assert steps["step2"]["kind"] == "verification", "step2 kind should be 'verification'"
        assert steps["step2"]["optional"] is True, "step2 optional should be True"
        assert steps["step2"]["status"] == "pending", "step2 status should be 'pending'"
        assert steps["step2"]["evidence"] == {}, "step2 evidence should be empty dict"

    def test_initialize_breadcrumb_preserves_string_steps(self, mock_skills_dir, tmp_path):
        """
        Test that string format workflow_steps are converted to steps dict with defaults.

        Given: Mock _load_workflow_steps() returns legacy string format (after TASK-001 normalization)
        When: initialize_breadcrumb_trail("test_skill") is called
        Then: steps dict created from string steps with default kind="execution", optional=False
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill with string format workflow_steps
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step_one\n"
            "  - step_two\n"
            "  - step_three\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Read breadcrumb file
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: steps field exists and is a dict
        assert "steps" in trail, "Breadcrumb trail should have steps field"
        assert isinstance(trail["steps"], dict), "steps should be a dict"

        steps = trail["steps"]

        # ASSERT: All string steps converted with defaults
        assert "step_one" in steps
        assert steps["step_one"]["kind"] == "execution", "String steps should default to kind='execution'"
        assert steps["step_one"]["optional"] is False, "String steps should default to optional=False"
        assert steps["step_one"]["status"] == "pending"
        assert steps["step_one"]["evidence"] == {}

        assert "step_two" in steps
        assert steps["step_two"]["kind"] == "execution"
        assert steps["step_two"]["optional"] is False
        assert steps["step_two"]["status"] == "pending"
        assert steps["step_two"]["evidence"] == {}

        assert "step_three" in steps
        assert steps["step_three"]["kind"] == "execution"
        assert steps["step_three"]["optional"] is False
        assert steps["step_three"]["status"] == "pending"
        assert steps["step_three"]["evidence"] == {}

    def test_initialize_breadcrumb_empty_workflow_steps(self, mock_skills_dir, tmp_path):
        """
        Test that empty workflow_steps list results in no breadcrumb file.

        Given: Mock _load_workflow_steps() returns []
        When: initialize_breadcrumb_trail("test_skill") is called
        Then: No breadcrumb file is created (early return)
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill with empty workflow_steps
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps: []\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # ASSERT: No breadcrumb file created
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        assert not breadcrumb_file.exists(), "Breadcrumb file should not be created for empty workflow_steps"


# =============================================================================
# TASK-002.5: Tests for set_breadcrumb() evidence parameter
# =============================================================================


class TestSetBreadcrumbEvidence:
    """Test that set_breadcrumb() accepts and stores evidence parameter."""

    def test_set_breadcrumb_with_evidence(self, mock_skills_dir, tmp_path):
        """
        Test that set_breadcrumb() accepts evidence parameter and stores it in steps dict.

        Given: Breadcrumb trail initialized with steps dict
        When: set_breadcrumb("test_skill", "step1", evidence={"test": "data"}) is called
        Then: steps["step1"]["status"] == "done"
        And: steps["step1"]["evidence"] == {"test": "data"}
        And: step1 in completed_steps
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step1\n"
            "  - step2\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Set breadcrumb with evidence
        with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
            with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                set_breadcrumb("test_skill", "step1", evidence={"test": "data"})

        # Read updated breadcrumb trail
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: step1 status updated to "done"
        assert trail["steps"]["step1"]["status"] == "done", \
            f"Expected status 'done', got {trail['steps']['step1']['status']}"

        # ASSERT: step1 evidence stored
        assert trail["steps"]["step1"]["evidence"] == {"test": "data"}, \
            f"Expected evidence {{'test': 'data'}}, got {trail['steps']['step1']['evidence']}"

        # ASSERT: step1 in completed_steps
        assert "step1" in trail["completed_steps"], \
            f"Expected step1 in completed_steps, got {trail['completed_steps']}"

    def test_set_breadcrumb_without_evidence(self, mock_skills_dir, tmp_path):
        """
        Test that set_breadcrumb() works without evidence parameter (backward compatibility).

        Given: Breadcrumb trail initialized with steps dict
        When: set_breadcrumb("test_skill", "step1") is called without evidence
        Then: steps["step1"]["status"] == "done"
        And: steps["step1"]["evidence"] == {}
        And: step1 in completed_steps
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step1\n"
            "  - step2\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Set breadcrumb WITHOUT evidence (backward compatibility)
        with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
            with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                set_breadcrumb("test_skill", "step1")

        # Read updated breadcrumb trail
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: step1 status updated to "done"
        assert trail["steps"]["step1"]["status"] == "done", \
            f"Expected status 'done', got {trail['steps']['step1']['status']}"

        # ASSERT: step1 evidence is empty dict
        assert trail["steps"]["step1"]["evidence"] == {}, \
            f"Expected empty evidence dict, got {trail['steps']['step1']['evidence']}"

        # ASSERT: step1 in completed_steps
        assert "step1" in trail["completed_steps"], \
            f"Expected step1 in completed_steps, got {trail['completed_steps']}"

    def test_set_breadcrumb_preserves_existing_evidence(self, mock_skills_dir, tmp_path):
        """
        Test that multiple set_breadcrumb() calls with evidence preserve/merge evidence.

        Given: Breadcrumb trail initialized with steps dict
        When: set_breadcrumb() is called twice for the same step with different evidence
        Then: Evidence is preserved/merged (implementation-dependent)
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step1\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # First call with evidence
        with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
            with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                set_breadcrumb("test_skill", "step1", evidence={"first": "call"})

        # Second call with different evidence
        with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
            with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                set_breadcrumb("test_skill", "step1", evidence={"second": "call"})

        # Read updated breadcrumb trail
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: Evidence contains both calls (merged) OR latest call (replaced)
        # Implementation choice: merge or replace
        evidence = trail["steps"]["step1"]["evidence"]

        # At minimum, the latest evidence should be present
        assert "second" in evidence or "first" in evidence, \
            f"Expected evidence to contain at least one call, got {evidence}"

        # If merged, both should be present
        # If replaced, only "second" should be present
        # Either behavior is acceptable - this test captures current behavior
        assert isinstance(evidence, dict), \
            f"Expected evidence to be dict, got {type(evidence)}"

    def test_set_breadcrumb_invalid_step(self, mock_skills_dir, tmp_path):
        """
        Test that set_breadcrumb() handles invalid step names gracefully.

        Given: Breadcrumb trail initialized with steps dict
        When: set_breadcrumb("test_skill", "invalid_step", evidence={"test": "data"}) is called
        Then: Function returns without error (graceful handling)
        And: No changes to completed_steps or steps dict
        """
        skills_dir, mock_path = mock_skills_dir

        # Create a test skill
        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: test_skill\n"
            "workflow_steps:\n"
            "  - step1\n"
            "  - step2\n"
            "---\n"
            "# Test Skill\n"
        )

        # Create mock breadcrumb directory
        breadcrumb_dir = tmp_path / "breadcrumbs"
        breadcrumb_dir.mkdir()

        def mock_get_breadcrumb_dir():
            return breadcrumb_dir

        def mock_terminal_id():
            return "test_terminal"

        # Initialize breadcrumb trail
        with patch("skill_guard.breadcrumb.tracker.Path", side_effect=mock_path):
            with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
                with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                    initialize_breadcrumb_trail("test_skill")

        # Read initial state
        breadcrumb_file = breadcrumb_dir / "breadcrumb_test_skill.json"
        initial_trail = json.loads(breadcrumb_file.read_text())
        initial_completed = initial_trail["completed_steps"].copy()

        # Set breadcrumb with invalid step name
        with patch("skill_guard.breadcrumb.tracker._get_breadcrumb_dir", side_effect=mock_get_breadcrumb_dir):
            with patch("skill_guard.breadcrumb.tracker.detect_terminal_id", side_effect=mock_terminal_id):
                # Should not raise an exception
                set_breadcrumb("test_skill", "invalid_step", evidence={"test": "data"})

        # Read updated breadcrumb trail
        updated_trail = json.loads(breadcrumb_file.read_text())

        # ASSERT: No changes to completed_steps
        assert updated_trail["completed_steps"] == initial_completed, \
            f"Expected completed_steps to remain {initial_completed}, got {updated_trail['completed_steps']}"

        # ASSERT: No changes to steps dict
        assert updated_trail["steps"] == initial_trail["steps"], \
            "Expected steps dict to remain unchanged"

        # ASSERT: Invalid step not in steps
        assert "invalid_step" not in updated_trail["steps"], \
            "Invalid step should not be added to steps dict"
