"""
Test suite to verify skills comply with Absence Claim Protocol.

This test enforces the verify-before-claiming pattern by checking that:
1. Skills reference verification_tiers.md Absence Claim Protocol
2. Skills have absence claim checks in quality gates
3. Protocol is discoverable (MEMORY.md index entry)

Evidence Tiers:
- Tier 2 (Component): Static analysis of skill files
- Tier 3 (Integration): Cross-skill pattern verification
"""

import re
from pathlib import Path

import pytest


def test_verification_tiers_protocol_exists():
    """Verify Absence Claim Protocol exists in verification_tiers.md."""
    verification_path = Path("C:/Users/brsth/.claude/projects/P--/memory/verification_tiers.md")

    content = verification_path.read_text()

    # Check for protocol section header
    assert "## Absence Claim Protocol" in content, "Missing Absence Claim Protocol section"

    # Check for key protocol elements (accept markdown headers and bold text)
    required_elements = [
        (r"\*\*Purpose\*\*:", "Purpose"),  # Bold markdown
        (r"###? Unverified Claim Patterns", "Unverified Claim Patterns"),  # Accept ### or plain
        (r"###? Compliant Claim Patterns", "Compliant Claim Patterns"),  # Accept ### or plain
        (r"## Evidence Requirements", "Evidence Requirements"),  # Accept ## or plain
    ]

    for pattern, element_name in required_elements:
        assert re.search(
            pattern, content, re.MULTILINE
        ), f"Missing protocol element: {element_name}"


def test_memory_index_references_protocol():
    """Verify MEMORY.md indexes verification_tiers.md with protocol description."""
    memory_path = Path("C:/Users/brsth/.claude/projects/P--/memory/MEMORY.md")

    content = memory_path.read_text()

    # Check that verification_tiers.md is in the table
    assert "verification_tiers.md" in content, "verification_tiers.md not indexed"

    # Check that index mentions Absence Claim Protocol
    assert (
        "Absence Claim Protocol" in content or "absence claim" in content.lower()
    ), "MEMORY.md doesn't mention Absence Claim Protocol in verification_tiers.md entry"


def test_skill_complete_has_absence_claim_check():
    """Verify skill-ship Phase 3 includes absence claim verification."""
    skill_complete_path = Path("P:/.claude/skills/skill-ship/SKILL.md")

    content = skill_complete_path.read_text()

    # Check for Phase 3 Quality Validation section
    assert "### Phase 3: Quality & Validation" in content, "Missing Phase 3 section"

    # Find the Quality Validation table
    quality_table_match = re.search(
        r"\|.*Test.*\|.*Status.*\|.*Evidence.*\|.*Fix.*\|.*\n(?:\|.*\n)*", content, re.MULTILINE
    )

    assert quality_table_match, "Could not find Quality Validation table"

    quality_table = quality_table_match.group(0)

    # Check for absence claim verification row
    assert re.search(
        r"absence claim", quality_table, re.IGNORECASE
    ), "Phase 3 Quality Validation table missing 'absence claim verification' row"


class TestSkillProtocolCompliance:
    """Test that key skills comply with verify-before-claiming protocol."""

    @pytest.fixture(
        params=[
            "P:/.claude/skills/r/SKILL.md",
            "P:/.claude/skills/pds/SKILL.md",
            "P:/.claude/skills/skill-ship/SKILL.md",
        ]
    )
    def skill_path(self, request):
        """Parametrized skill paths to test."""
        return Path(request.param)

    @pytest.fixture
    def skill_content(self, skill_path):
        """Load skill content."""
        return skill_path.read_text()

    def test_references_verification_tiers(self, skill_content, skill_path):
        """Verify skill references verification_tiers.md protocol."""
        # Check for direct protocol reference
        has_protocol_ref = bool(
            re.search(
                r"verification_tiers\.md.*Absence Claim Protocol", skill_content, re.IGNORECASE
            )
        )

        # Or check for generic verification_tiers reference
        has_verification_ref = "verification_tiers.md" in skill_content

        assert (
            has_protocol_ref or has_verification_ref
        ), f"{skill_path.name} doesn't reference verification_tiers.md or Absence Claim Protocol"

    def test_has_verification_workflow(self, skill_content, skill_path):
        """Verify skill has verification workflow in critical sections."""
        # Look for verification patterns in key sections
        verification_keywords = [
            r"verify.*absence",
            r"check.*before.*claim",
            r"search.*before.*stat",
            r"Grep.*before.*claim",
            r"Read.*before.*missing",
        ]

        has_verification_workflow = any(
            re.search(pattern, skill_content, re.IGNORECASE) for pattern in verification_keywords
        )

        assert (
            has_verification_workflow
        ), f"{skill_path.name} doesn't have explicit verification workflow for absence claims"


def test_arch_skill_has_verification_guidance():
    """Verify /arch skill has verification guidance in precedent.md."""
    precedent_path = Path("P:/packages/arch/skill/resources/precedent.md")

    content = precedent_path.read_text()

    # Check for verification requirement
    has_verification = bool(
        re.search(
            r"verify.*absence.*claim|verify.*before.*missing|verification_tiers\.md",
            content,
            re.IGNORECASE,
        )
    )

    assert has_verification, (
        "precedent.md doesn't instruct to verify absence claims "
        "before stating components are missing"
    )


@pytest.mark.integration
class TestProtocolEffectiveness:
    """
    Integration tests to measure protocol effectiveness.

    These tests require:
    - Access to StopHook execution logs
    - Baseline metrics (before protocol implementation)
    - Current metrics (after protocol implementation)

    Run with: pytest --runxfail -xvs to see expected failures
    """

    def test_stop_hook_block_rate_decreased(self):
        """
        Test that StopHook block rate decreased after protocol implementation.

        Prerequisites:
        1. Baseline: StopHook blocked X% of responses before protocol
        2. Current: StopHook blocks Y% of responses after protocol
        3. Expected: Y < X (decreased block rate)

        How to measure:
        - Count StopHook blocks in logs from date range
        - Calculate blocks per 100 responses
        - Compare before/after 2026-03-14 (protocol date)
        """
        pytest.xfail(
            "Requires StopHook execution logs to measure block rate change. "
            "Run: grep -r 'Unverified Negative Existence Claim Detected' "
            "   .claude/history/*.jsonl | "
            "   jq -r '.timestamp' | "
            "   awk -F'T' '{print $1}' | "
            "   sort | uniq -c"
        )

    def test_protocol_compliance_rate_measured(self):
        """
        Test that we can measure what % of skills comply with protocol.

        Metrics:
        - Total skills in codebase
        - Skills that reference verification_tiers.md
        - Skills that have absence claim checks
        - Compliance % = (compliant_skills / total_skills) * 100

        Target: 100% compliance for skills that make system claims
        """
        pytest.xfail(
            "Requires automated scan of all skills to measure compliance rate. "
            "Run: grep -l 'verification_tiers.md' "
            "   .claude/skills/*/SKILL.md "
            "   packages/*/skill/SKILL.md | wc -l"
        )


if __name__ == "__main__":
    # Run component tests (fast, no external dependencies)
    pytest.main([__file__, "-v", "-k", "not integration"])

    # To run integration tests (requires logs):
    # pytest __file__ --runxfail -xvs
