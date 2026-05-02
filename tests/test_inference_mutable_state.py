"""
Characterization tests for add_tool_mapping() mutable state bug.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
The bug: add_tool_mapping() mutates DEFAULT_TOOL_MAPPINGS at runtime with no locking.

Run with: pytest P:/packages/skill-guard/tests/test_inference_mutable_state.py -v
"""

import pytest
from skill_guard.breadcrumb.inference import (
    add_tool_mapping,
    infer_step_from_tool_use,
    DEFAULT_TOOL_MAPPINGS,
)


class TestAddToolMappingMutableState:
    """Tests that capture the mutable state bug in add_tool_mapping()."""

    def test_add_tool_mapping_mutates_module_level_dict(self):
        """Characterization: add_tool_mapping() directly mutates DEFAULT_TOOL_MAPPINGS.

        Given: DEFAULT_TOOL_MAPPINGS is a module-level dict
        When: add_tool_mapping("CustomTool", "custom_step") is called
        Then: DEFAULT_TOOL_MAPPINGS itself is mutated (not a copy)
        """
        initial_keys = set(DEFAULT_TOOL_MAPPINGS.keys())
        assert "CustomTool" not in initial_keys

        add_tool_mapping("CustomTool", "custom_step")

        # BUG: The module-level dict is directly mutated
        assert "CustomTool" in DEFAULT_TOOL_MAPPINGS
        assert DEFAULT_TOOL_MAPPINGS["CustomTool"] == "custom_step"

    def test_mutation_is_observable_after_call(self):
        """Characterization: The mutation is observable via get_supported_tools().

        Given: A fresh inference module
        When: add_tool_mapping() is called
        Then: get_supported_tools() returns the modified mapping
        """
        custom_tool = "TestObservableTool"
        custom_step = "test_step"

        add_tool_mapping(custom_tool, custom_step)

        from skill_guard.breadcrumb.inference import get_supported_tools
        supported = get_supported_tools()

        # BUG: The mutation is globally observable
        assert custom_tool in supported

    def test_multiple_calls_produce_different_results(self):
        """Characterization: add_tool_mapping() is not idempotent - calls accumulate.

        Given: DEFAULT_TOOL_MAPPINGS with N tools
        When: add_tool_mapping("ToolA", "step_a") and add_tool_mapping("ToolB", "step_b") are called
        Then: Both tools remain in DEFAULT_TOOL_MAPPINGS (mutations accumulate)
        """
        tool_a = "AccumToolA"
        tool_b = "AccumToolB"

        add_tool_mapping(tool_a, "step_a")
        add_tool_mapping(tool_b, "step_b")

        # BUG: Both mutations persist - no isolation between calls
        assert tool_a in DEFAULT_TOOL_MAPPINGS
        assert tool_b in DEFAULT_TOOL_MAPPINGS
        assert DEFAULT_TOOL_MAPPINGS[tool_a] == "step_a"
        assert DEFAULT_TOOL_MAPPINGS[tool_b] == "step_b"

    def test_infer_step_reflects_custom_mapping(self):
        """Characterization: Custom mappings affect infer_step_from_tool_use().

        Given: A custom tool mapping
        When: infer_step_from_tool_use() is called with that tool
        Then: The custom step is returned (proving global mutation)
        """
        custom_tool = "MyCustomInfTool"
        custom_step = "custom_inference"

        add_tool_mapping(custom_tool, custom_step)

        result = infer_step_from_tool_use(custom_tool, {})

        # BUG: The custom mapping affects the global inference
        assert result == custom_step

    def test_mutation_affects_all_callers(self):
        """Characterization: Mutation is visible to all code using the module.

        This test captures that DEFAULT_TOOL_MAPPINGS is a shared global state
        that gets modified by add_tool_mapping(), affecting all callers.
        """
        # Add a mapping
        shared_tool = "SharedMutTool"
        add_tool_mapping(shared_tool, "shared_step")

        # The mapping is now visible to any code importing this module
        from skill_guard.breadcrumb.inference import DEFAULT_TOOL_MAPPINGS as mappings

        # BUG: All code see the same mutated state
        assert shared_tool in mappings