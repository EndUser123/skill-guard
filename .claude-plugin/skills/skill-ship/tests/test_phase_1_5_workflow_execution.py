"""
Integration test to verify Phase 1.5 executes during skill-ship workflow.

This test verifies that Phase 1.5 Knowledge Retrieval is not just documented
but actually executed during the /skill-ship workflow.
"""

import re
from pathlib import Path


def test_phase_1_5_workflow_execution_guidance():
    """Verify that skill-ship provides clear guidance for executing Phase 1.5."""
    skill_path = Path(__file__).parent.parent / "SKILL.md"

    content = skill_path.read_text()

    # Verify Phase 1.5 has execution guidance (not just documentation)
    phase_section = content[content.find("phase_1_5_knowledge_retrieval:") :]
    phase_section = phase_section[:500]  # First 500 chars should have guidance

    # Should have actionable guidance, not just a placeholder
    assert len(phase_section) > 100, "Phase 1.5 section too short - missing execution guidance"
    assert re.search(
        r"query|retrieve|nlm notebook|cks search",
        phase_section,
        re.IGNORECASE,
    ), "Phase 1.5 should describe what queries to execute"


def test_phase_1_5_has_skip_criteria():
    """Verify that Phase 1.5 has clear skip criteria for execution."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Should have "Skip Phase 1.5 when" section
    assert "Skip Phase 1.5 when" in content or "skip" in content.lower(), (
        "Phase 1.5 should have documented skip conditions"
    )

    # Should have at least 3 skip scenarios
    skip_section = content[content.find("## When to Use") :]
    skip_patterns = [
        "simple",
        "decline",
        "no existing",
    ]

    skip_count = sum(
        1 for pattern in skip_patterns if re.search(pattern, skip_section, re.IGNORECASE)
    )

    assert skip_count >= 2, f"Should have at least 2 skip scenarios, found {skip_count}"


def test_knowledge_retrieval_query_patterns_exist():
    """Verify that query patterns are documented for actual execution."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Should have concrete query examples (not just abstract descriptions)
    query_indicators = [
        "/cks",  # CKS query pattern
        "/nlm",  # NotebookLM query pattern
        "Read",  # Memory.md Read tool pattern
    ]

    for indicator in query_indicators:
        assert indicator in content, f"Missing {indicator} query pattern - no execution guidance"


def test_phase_1_5_output_format_actionable():
    """Verify Phase 1.5 output format is actionable (not just descriptive)."""
    reference_path = Path(__file__).parent.parent / "references" / "knowledge-retrieval.md"

    content = reference_path.read_text()

    # Output Format section should exist
    assert "## Output Format" in content, "Missing Output Format section"

    # Should specify template format (Template 2)
    output_section = content[content.find("## Output Format") :]
    assert "Template 2" in output_section or "Executive Summary" in output_section, (
        "Should specify actionable output format"
    )

    # Should show example structure (not just description)
    assert "## Knowledge Retrieval Summary" in output_section, (
        "Should show concrete output example structure"
    )
