r"""
Characterization tests for add_tool_mapping() mutable state bug.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
The bug: add_tool_mapping() mutates DEFAULT_TOOL_MAPPINGS at runtime with no locking.

Run with: pytest P:\\\\\\packages/skill-guard/tests/test_inference_mutable_state.py -v
"""

import pytest
from skill_guard.breadcrumb.inference import (
    add_tool_mapping,
    infer_step_from_tool_use,
    DEFAULT_TOOL_MAPPINGS,
)


class TestAddToolMappingMutableState:
    """Tests that capture the mutable state bug in add_tool_mapping()."""

    def test_add_tool_mapping_uses_runtime_mappings(self):
        """Fixed behavior: add_tool_mapping() writes to _RUNTIME_MAPPINGS, not DEFAULT_TOOL_MAPPINGS."""
        from skill_guard.breadcrumb.inference import _RUNTIME_MAPPINGS

        initial_runtime_keys = set(_RUNTIME_MAPPINGS.keys())
        assert "CustomTool" not in initial_runtime_keys

        add_tool_mapping("CustomTool", "custom_step")

        # FIXED: Now writes to _RUNTIME_MAPPINGS, not the module-level DEFAULT_TOOL_MAPPINGS
        assert "CustomTool" in _RUNTIME_MAPPINGS
        assert _RUNTIME_MAPPINGS["CustomTool"] == "custom_step"
        # DEFAULT_TOOL_MAPPINGS should NOT be mutated
        assert "CustomTool" not in DEFAULT_TOOL_MAPPINGS

    def test_mutation_via_runtime_mappings_is_observable(self):
        """Fixed behavior: Custom mappings are observable via get_supported_tools() through _RUNTIME_MAPPINGS."""
        custom_tool = "TestObservableTool"
        custom_step = "test_step"

        add_tool_mapping(custom_tool, custom_step)

        from skill_guard.breadcrumb.inference import get_supported_tools
        supported = get_supported_tools()

        # FIXED: The custom mapping is still observable (via merged runtime mappings)
        assert custom_tool in supported

    def test_multiple_calls_accumulate_in_runtime_mappings(self):
        """Fixed behavior: add_tool_mapping() accumulates in _RUNTIME_MAPPINGS, not DEFAULT_TOOL_MAPPINGS."""
        from skill_guard.breadcrumb.inference import _RUNTIME_MAPPINGS

        tool_a = "AccumToolA"
        tool_b = "AccumToolB"

        add_tool_mapping(tool_a, "step_a")
        add_tool_mapping(tool_b, "step_b")

        # FIXED: Both mutations accumulate in _RUNTIME_MAPPINGS
        assert tool_a in _RUNTIME_MAPPINGS
        assert tool_b in _RUNTIME_MAPPINGS
        assert _RUNTIME_MAPPINGS[tool_a] == "step_a"
        assert _RUNTIME_MAPPINGS[tool_b] == "step_b"

    def test_infer_step_reflects_runtime_mapping(self):
        """Fixed behavior: Custom mappings affect infer_step_from_tool_use() via _RUNTIME_MAPPINGS."""
        custom_tool = "MyCustomInfTool"
        custom_step = "custom_inference"

        add_tool_mapping(custom_tool, custom_step)

        result = infer_step_from_tool_use(custom_tool, {})

        # FIXED: The custom mapping still affects the global inference (via _RUNTIME_MAPPINGS)
        assert result == custom_step

    def test_runtime_mappings_isolated_from_default(self):
        """Fixed behavior: _RUNTIME_MAPPINGS is isolated — DEFAULT_TOOL_MAPPINGS unchanged."""
        shared_tool = "SharedMutTool"
        add_tool_mapping(shared_tool, "shared_step")

        # FIXED: DEFAULT_TOOL_MAPPINGS is NOT mutated
        from skill_guard.breadcrumb.inference import DEFAULT_TOOL_MAPPINGS as mappings
        assert shared_tool not in mappings
        # But it IS in _RUNTIME_MAPPINGS and get_supported_tools()
        from skill_guard.breadcrumb.inference import _RUNTIME_MAPPINGS
        assert shared_tool in _RUNTIME_MAPPINGS