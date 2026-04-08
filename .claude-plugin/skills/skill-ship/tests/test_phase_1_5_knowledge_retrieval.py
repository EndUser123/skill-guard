"""
Test suite to verify Phase 1.5 Knowledge Retrieval implementation.

This test enforces that Phase 1.5 Knowledge Retrieval is properly documented
and operationally verified. Tests cover:

1. Phase 1.5 documented in SKILL.md workflow_steps
2. knowledge-retrieval.md reference exists with proper content
3. Security patterns: Skill tool usage instead of bash commands
4. Skip conditions are clearly documented
5. Enforcement directive exists in SKILL.md

Evidence Tiers:
- Tier 2 (Component): Static analysis of skill files
- Tier 3 (Integration): Cross-skill pattern verification
"""

import re
from pathlib import Path


def test_phase_1_5_in_workflow_steps():
    """Verify Phase 1.5 Knowledge Retrieval is in SKILL.md workflow_steps."""
    skill_path = Path(__file__).parent.parent / "SKILL.md"

    content = skill_path.read_text()

    # Check for phase_1_5_knowledge_retrieval in workflow_steps
    assert (
        "phase_1_5_knowledge_retrieval:" in content
    ), "Phase 1.5 Knowledge Retrieval not found in workflow_steps"

    # Verify it appears before phase_2_creation (order matters)
    workflow_section = content[
        content.find("workflow_steps:") : content.find("workflow_steps:") + 1000
    ]
    phase_1_5_pos = workflow_section.find("phase_1_5_knowledge_retrieval")
    phase_2_pos = workflow_section.find("phase_2_creation")

    assert phase_1_5_pos > 0, "Phase 1.5 not found in workflow_steps"
    assert phase_2_pos > 0, "Phase 2 not found in workflow_steps"
    assert phase_1_5_pos < phase_2_pos, "Phase 1.5 should appear before Phase 2"


def test_enforcement_directive_exists():
    """Verify SKILL.md has enforcement directive for workflow compliance."""
    skill_path = Path(__file__).parent.parent / "SKILL.md"

    content = skill_path.read_text()

    # Check for enforcement field in frontmatter
    assert "enforcement:" in content, "Missing enforcement field in SKILL.md frontmatter"

    # Verify enforcement is one of the valid values
    enforcement_match = re.search(r"enforcement:\s*(strict|advisory|none)", content)
    assert (
        enforcement_match is not None
    ), "Invalid enforcement value, must be strict, advisory, or none"

    # For skill-ship, advisory is appropriate (can skip but should execute)
    enforcement_value = enforcement_match.group(1)
    assert enforcement_value in [
        "advisory",
        "strict",
    ], f"enforcement: {enforcement_value} - advisory or strict recommended for skill-ship"


def test_knowledge_retrieval_reference_exists():
    """Verify knowledge-retrieval.md reference documentation exists."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    assert (
        reference_path.exists()
    ), f"knowledge-retrieval.md reference not found at {reference_path}"

    content = reference_path.read_text()

    # Check for key sections
    required_sections = [
        ("# Knowledge Retrieval Guide", "Main title"),
        ("## Purpose", "Purpose section"),
        ("## When to Use", "When to Use section"),
        ("## Query Patterns", "Query Patterns section"),
        ("## Output Format", "Output Format section"),
        ("## Key Principles", "Key Principles section"),
    ]

    for section, description in required_sections:
        assert section in content, f"Missing section in knowledge-retrieval.md: {description}"


def test_security_patterns_skill_tool_not_bash():
    """Verify knowledge-retrieval.md uses Skill tool instead of bash commands."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Check that NotebookLM examples use /nlm (Skill tool) not bash nlm
    # Should have /nlm not "nlm" in bash code blocks
    notebooklm_section = content[content.find("### NotebookLM Query Pattern") :]
    notebooklm_section = (
        notebooklm_section[: notebooklm_section.find("###", 3)]
        if "###" in notebooklm_section[100:]
        else notebooklm_section
    )

    # Should use markdown code blocks (```), not bash blocks (```bash)
    # and should show /nlm skill invocations
    assert "/nlm auth status" in notebooklm_section, "Missing safe /nlm auth status example"
    assert "/nlm notebook list" in notebooklm_section, "Missing safe /nlm notebook list example"
    assert "/nlm notebook query" in notebooklm_section, "Missing safe /nlm notebook query example"

    # Verify Security Note exists
    assert "Security Note" in notebooklm_section, "Missing Security Note about Skill tool usage"


def test_cross_platform_path_examples():
    """Verify memory.md examples use cross-platform paths."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Find memory.md query pattern section
    memory_section = content[content.find("### Memory.md Query Pattern") :]
    memory_section = (
        memory_section[: memory_section.find("###", 3)]
        if "###" in memory_section[100:]
        else memory_section
    )

    # Should use cross-platform path examples (~/.claude/)
    # Not hard-coded Windows paths (C:\Users\brsth\...)
    assert "~/.claude/" in memory_section, "Missing cross-platform path example (~/.claude/)"

    # Should have Cross-Platform Note
    assert (
        "Cross-Platform Note" in memory_section
    ), "Missing Cross-Platform Note about path variations"


def test_skip_conditions_documented():
    """Verify skip conditions are clearly documented."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Check for "Skip Phase 1.5 when" section
    assert (
        "Skip Phase 1.5 when" in content or "## When to Use" in content
    ), "Missing skip conditions documentation"

    # Verify at least 3 skip conditions are documented
    skip_section = content[content.find("## When to Use") :]
    skip_patterns = [
        r"simple skills",
        r"user explicitly declines",
        r"no existing CKS",
    ]

    for pattern in skip_patterns:
        assert re.search(
            pattern, skip_section, re.IGNORECASE
        ), f"Missing skip condition pattern: {pattern}"


def test_output_format_template_2():
    """Verify knowledge-retrieval.md specifies Template 2 output format."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Check for Output Format section with Template 2
    assert "## Output Format" in content, "Missing Output Format section"

    # Extract Output Format section up to "## Key Principles" (the next major section)
    output_section = content[content.find("## Output Format") :]
    key_principles_pos = output_section.find("\n## Key Principles")
    if key_principles_pos > 0:
        output_section = output_section[:key_principles_pos]

    # Should mention Template 2 (Executive Summary Format)
    assert (
        "Template 2" in output_section or "Executive Summary Format" in output_section
    ), "Should specify Template 2 (Executive Summary Format)"

    # Should show the expected output structure
    assert (
        "## Knowledge Retrieval Summary" in output_section
    ), "Missing '## Knowledge Retrieval Summary' output example"


def test_recommendations_not_requirements():
    """Verify knowledge retrieval findings are recommendations, not requirements."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Key Principles section should emphasize recommendations over requirements
    assert "## Key Principles" in content, "Missing Key Principles section"

    principles_section = content[content.find("## Key Principles") :]
    principles_section = (
        principles_section[: principles_section.find("##", 3)]
        if "##" in principles_section[100:]
        else principles_section
    )

    # Should mention "recommendations, not requirements"
    assert re.search(
        r"recommendations.*not.*requirements", principles_section, re.IGNORECASE
    ), "Should emphasize findings are recommendations, not requirements"


def test_skill_ship_workflow_phase_order():
    """Verify Phase 1.5 appears in correct position in workflow."""
    skill_path = Path(__file__).parent.parent / "SKILL.md"

    content = skill_path.read_text()

    # Find workflow_steps section
    workflow_start = content.find("workflow_steps:")
    workflow_end = content.find("---", workflow_start + 1)
    workflow_content = content[workflow_start:workflow_end]

    # Verify phase order: 0 → 1 → 1.5 → 2
    phases = [
        ("phase_0_context:", 0),
        ("phase_1_discovery:", 1),
        ("phase_1_5_knowledge_retrieval:", 1.5),
        ("phase_2_creation:", 2),
    ]

    phase_positions = {}
    for phase_name, expected_number in phases:
        pos = workflow_content.find(phase_name)
        assert pos > 0, f"Phase {phase_name} not found in workflow_steps"
        phase_positions[expected_number] = pos

    # Verify order: 0 < 1 < 1.5 < 2
    assert phase_positions[0] < phase_positions[1], "Phase 0 should come before Phase 1"
    assert phase_positions[1] < phase_positions[1.5], "Phase 1 should come before Phase 1.5"
    assert phase_positions[1.5] < phase_positions[2], "Phase 1.5 should come before Phase 2"
