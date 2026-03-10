#!/usr/bin/env python3
"""
Test suite for tool pattern inference system

Acceptance Criteria:
- Test inference of workflow steps from tool names
- Test normalization of step names
- Test custom tool mappings
- Test unmapped tools return None
- Test special inference rules for tool patterns
"""

import pytest

from skill_guard.breadcrumb.inference import (
    DEFAULT_TOOL_MAPPINGS,
    _normalize_step_name,
    add_tool_mapping,
    get_supported_tools,
    infer_step_from_tool_use,
    remove_tool_mapping,
)


class TestToolInference:
    """Test tool pattern inference."""

    def test_research_tools_mapped_to_research(self):
        """Test that research tools map to 'research' step."""
        research_tools = [
            "WebSearch",
            "mcp__tavily-mcp__tavily_search",
            "mcp__tavily-mcp__tavily_research",
            "mcp__perplexity__perplexity_search",
            "mcp__perplexity__perplexity_ask",
            "mcp__perplexity__perplexity_research",
            "mcp__exa__get_code_context_exa",
        ]

        for tool in research_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step == "research", f"Tool {tool} should map to 'research', got {step}"

    def test_requirements_tools_mapped_to_requirements(self):
        """Test that requirements tools map to 'requirements' step."""
        requirements_tools = [
            "Read",
            "Glob",
            "Grep",
            "LSP",
        ]

        for tool in requirements_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step == "requirements", f"Tool {tool} should map to 'requirements', got {step}"

    def test_tdd_tools_mapped_to_tdd(self):
        """Test that TDD tools map to 'tdd' step."""
        tdd_tools = [
            "Edit",
            "Write",
            "NotebookEdit",
        ]

        for tool in tdd_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step == "tdd", f"Tool {tool} should map to 'tdd', got {step}"

    def test_verification_tools_mapped_to_verification(self):
        """Test that verification tools map to 'verification' step."""
        verification_tools = [
            "Bash",
            "Skill",
        ]

        for tool in verification_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step == "verification", f"Tool {tool} should map to 'verification', got {step}"

    def test_planning_tools_mapped_to_planning(self):
        """Test that planning tools map to 'planning' step."""
        planning_tools = [
            "AskUserQuestion",
            "EnterPlanMode",
            "ExitPlanMode",
        ]

        for tool in planning_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step == "planning", f"Tool {tool} should map to 'planning', got {step}"

    def test_agent_tools_mapped_to_agent_coordination(self):
        """Test that agent tools map to 'agent_coordination' step."""
        step = infer_step_from_tool_use("Agent", {})
        assert step == "agent_coordination"

    def test_unmapped_tool_returns_none(self):
        """Test that unmapped tools return None."""
        unmapped_tools = [
            "UnknownTool",
            "SomeRandomTool",
            "NotMappedTool",
        ]

        for tool in unmapped_tools:
            step = infer_step_from_tool_use(tool, {})
            assert step is None, f"Tool {tool} should return None, got {step}"

    def test_step_name_normalization(self):
        """Test that step names are normalized correctly."""
        # Test lowercase conversion
        assert _normalize_step_name("Research") == "research"
        assert _normalize_step_name("TDD") == "tdd"

        # Test space to underscore conversion
        assert _normalize_step_name("step name") == "step_name"
        assert _normalize_step_name("My Custom Step") == "my_custom_step"

        # Test hyphen to underscore conversion
        assert _normalize_step_name("step-name") == "step_name"
        assert _normalize_step_name("my-custom-step") == "my_custom_step"

    def test_custom_tool_mapping(self):
        """Test adding custom tool mappings."""
        # Add custom mapping
        add_tool_mapping("MyCustomTool", "custom_step")

        # Test mapping works
        step = infer_step_from_tool_use("MyCustomTool", {})
        assert step == "custom_step"

        # Clean up
        remove_tool_mapping("MyCustomTool")

        # Verify mapping is removed
        step = infer_step_from_tool_use("MyCustomTool", {})
        assert step is None

    def test_get_supported_tools(self):
        """Test getting list of supported tools."""
        supported = get_supported_tools()

        # Verify it's a list
        assert isinstance(supported, list)

        # Verify it contains expected tools
        assert "WebSearch" in supported
        assert "Read" in supported
        assert "Edit" in supported
        assert "Bash" in supported

        # Verify all tools have mappings
        for tool in supported:
            assert tool in DEFAULT_TOOL_MAPPINGS

    def test_tool_input_ignored_for_basic_tools(self):
        """Test that tool_input doesn't affect inference for basic tools."""
        # Same tool, different inputs should give same result
        step1 = infer_step_from_tool_use("Read", {"file_path": "test.py"})
        step2 = infer_step_from_tool_use("Read", {"file_path": "other.py"})

        assert step1 == step2 == "requirements"

    def test_pattern_based_inference_for_search_tools(self):
        """Test pattern-based inference for tools with 'search' in name."""
        # Custom search tool not in explicit mappings
        step = infer_step_from_tool_use("CustomSearchTool", {})
        assert step == "research"

    def test_pattern_based_inference_for_read_tools(self):
        """Test pattern-based inference for tools with 'read' in name."""
        # Custom read tool not in explicit mappings
        step = infer_step_from_tool_use("CustomReadTool", {})
        assert step == "requirements"

    def test_pattern_based_inference_for_edit_tools(self):
        """Test pattern-based inference for tools with 'edit' in name."""
        # Custom edit tool not in explicit mappings
        step = infer_step_from_tool_use("CustomEditTool", {})
        assert step == "tdd"

    def test_exact_match_takes_precedence_over_pattern(self):
        """Test that exact mappings take precedence over pattern matching."""
        # "search" in name would match "research" pattern
        # But exact mapping should take precedence
        step = infer_step_from_tool_use("WebSearch", {})
        assert step == "research"  # From exact mapping

    def test_inference_with_mcp_prefix(self):
        """Test that MCP tool prefixes are handled correctly."""
        # MCP tools with full prefix
        step = infer_step_from_tool_use("mcp__tavily-mcp__tavily_search", {})
        assert step == "research"

        step = infer_step_from_tool_use("mcp__perplexity__perplexity_ask", {})
        assert step == "research"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
