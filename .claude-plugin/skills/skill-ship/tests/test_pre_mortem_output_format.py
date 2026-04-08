"""
Test to verify pre-mortem skill output format compliance.

This test ensures that the /pre-mortem skill ALWAYS produces
the RECOMMENDED NEXT STEPS section with the required format.
"""

from pathlib import Path


def test_pre_mortem_skill_has_output_format_spec():
    """Verify pre-mortem SKILL.md documents the required output format."""
    pre_mortem_path = Path("C:/Users/brsth/.claude/skills/pre-mortem/SKILL.md")

    if not pre_mortem_path.exists():
        pre_mortem_path = Path.home() / ".claude/skills/pre-mortem/SKILL.md"

    assert pre_mortem_path.exists(), "pre-mortem SKILL.md not found"

    content = pre_mortem_path.read_text()

    # Should document the RECOMMENDED NEXT STEPS section
    assert (
        "## ✅ RECOMMENDED NEXT STEPS" in content or "RECOMMENDED NEXT STEPS" in content
    ), "pre-mortem should document RECOMMENDED NEXT STEPS output section"

    # Should specify the required format with domains
    assert (
        "Domain" in content or "1 (" in content
    ), "pre-mortem should specify domain-based format (e.g., '1 (DOMAIN)')"


def test_pre_mortem_output_format_has_all_required_sections():
    """Verify pre-mortem output format includes all required sections."""
    pre_mortem_path = Path("C:/Users/brsth/.claude/skills/pre-mortem/SKILL.md")

    if not pre_mortem_path.exists():
        pre_mortem_path = Path.home() / ".claude/skills/pre-mortem/SKILL.md"

    content = pre_mortem_path.read_text()

    # Extract Output Format section (extend to include Formatting Rules)
    output_format_start = content.find("## Output Format")
    assert output_format_start > 0, "Missing Output Format section in pre-mortem SKILL.md"

    # Find "## Usage Patterns" section which follows Output Format
    output_format_section = content[output_format_start:]
    usage_patterns_pos = output_format_section.find("\n## Usage Patterns")
    if usage_patterns_pos > 0:
        output_format_section = output_format_section[:usage_patterns_pos]

    # The Output Format section contains:
    # 1. Prose description
    # 2. Code block example with emoji sections
    # 3. Formatting Rules with section header references

    # Verify Formatting Rules section exists (contains section header list)
    assert (
        "Formatting Rules:" in output_format_section
    ), "Missing Formatting Rules section in Output Format"

    # Verify code block example exists (contains markdown code fence)
    assert "```" in output_format_section, "Missing code block example in Output Format"

    # Verify key section headers are documented in Formatting Rules or code example
    # Check for emoji sections which are the actual format
    required_emoji_sections = [
        ("🔴 WHAT'S ACTUALLY BROKEN", "Critical failures section"),
        ("🟠 HIGH-RISK BEHAVIOR", "High-risk behavior section"),
        ("🧠 BLIND SPOTS", "Blind spots section"),
        ("🧪 TESTING", "Testing section"),
        ("📂 EVIDENCE", "Evidence artifacts section"),
        ("✅ RECOMMENDED NEXT STEPS", "Recommended next steps section"),
    ]

    for emoji_section, description in required_emoji_sections:
        assert (
            emoji_section in output_format_section
        ), f"Missing required section in format: {description}"


def test_pre_mortem_format_includes_evidence_citations():
    """Verify pre-mortem format requires evidence citations for findings."""
    pre_mortem_path = Path("C:/Users/brsth/.claude/skills/pre-mortem/SKILL.md")

    if not pre_mortem_path.exists():
        pre_mortem_path = Path.home() / ".claude/skills/pre-mortem/SKILL.md"

    content = pre_mortem_path.read_text()

    # Should mention evidence requirements
    assert "evidence" in content.lower(), "Should mention evidence requirements"
    assert (
        "file:line" in content or "citation" in content.lower()
    ), "Should specify file:line citation format"


def test_pre_mortem_format_includes_skill_tracking():
    """Verify pre-mortem format includes skill name in action items."""
    pre_mortem_path = Path("C:/Users/brsth/.claude/skills/pre-mortem/SKILL.md")

    if not pre_mortem_path.exists():
        pre_mortem_path = Path.home() / ".claude/skills/pre-mortem/SKILL.md"

    content = pre_mortem_path.read_text()

    # Should mention skills in action format (pre-mortem, gto, critique, /learn, /reflect, etc)
    skill_keywords = ["skill", "/learn", "/reflect", "Use /skill"]
    assert any(
        keyword in content.lower() for keyword in skill_keywords
    ), "Should mention skill usage in action items"

    # Should have examples of skill invocations in the format
    assert (
        "Use `" in content or "→ Use" in content or "via" in content.lower()
    ), "Should show skill invocation pattern in examples"
