"""Context size validation for skill-ship Phase 3b (Code Quality).

This module validates SKILL.md files for context bloat prevention:
- Line count validation (warn >300 lines, block >500 lines)
- Duplicate content detection (against memory/ files)
- Reference integrity (all references/ links exist)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# Validation thresholds
_WARN_LINE_COUNT = 300
_FAIL_LINE_COUNT = 500
_MIN_BLOCK_LINES = 3
_MAX_MEMORY_SEARCH_LEVELS = 5


@dataclass
class ValidationResult:
    """Result of context size validation.

    Attributes:
        status: Validation status - "pass", "warn", or "fail"
        findings: List of validation messages
        line_count: Number of lines in SKILL.md
        duplicate_count: Number of duplicate content matches found
        broken_references: List of missing reference files
    """

    status: str  # "pass", "warn", "fail"
    findings: list[str] = field(default_factory=list)
    line_count: int = 0
    duplicate_count: int = 0
    broken_references: list[str] = field(default_factory=list)


def validate_context_size(skill_path: str) -> ValidationResult:
    """Validate SKILL.md for context bloat prevention.

    Args:
        skill_path: Path to the skill directory containing SKILL.md

    Returns:
        ValidationResult with validation status and findings
    """
    path = Path(skill_path)

    # Check if SKILL.md exists
    skill_file = path / "SKILL.md"
    if not skill_file.exists():
        return ValidationResult(status="fail", findings=[f"SKILL.md not found at {skill_file}"])

    # Read and count lines
    try:
        content = skill_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        line_count = len(lines)
    except Exception as e:
        return ValidationResult(status="fail", findings=[f"Error reading SKILL.md: {e}"])

    findings = []
    status = "pass"
    duplicate_count = 0
    broken_references = []

    # Check line count thresholds
    if line_count > _FAIL_LINE_COUNT:
        status = "fail"
        findings.append(
            f"SKILL.md exceeds {_FAIL_LINE_COUNT} lines ({line_count} lines). "
            "Extract content to references/ before proceeding."
        )
    elif line_count > _WARN_LINE_COUNT:
        status = "warn"
        findings.append(
            f"SKILL.md is {line_count} lines. Extract content to references/ recommended."
        )

    # Check for duplicate content (optional - may be expensive)
    # This is a simple implementation - could be enhanced with fuzzy matching
    duplicate_count = _check_duplicates(path, content)
    if duplicate_count > 0:
        if status == "pass":
            status = "warn"
        findings.append(
            f"Found {duplicate_count} potential duplicate(s) with memory/ files. "
            "Consider progressive disclosure."
        )

    # Check reference integrity
    broken_references = _check_references(path, content)
    if broken_references:
        if status == "pass":
            status = "warn"
        findings.append(
            f"Broken references: {', '.join(broken_references)}. Update or remove these links."
        )

    return ValidationResult(
        status=status,
        findings=findings,
        line_count=line_count,
        duplicate_count=duplicate_count,
        broken_references=broken_references,
    )


def _check_duplicates(skill_path: Path, skill_content: str) -> int:
    """Check for duplicate content against memory/ files.

    This is a simplified implementation that looks for exact matches
    of substantial content blocks (3+ lines).

    Args:
        skill_path: Path to the skill directory
        skill_content: Content of SKILL.md

    Returns:
        Number of duplicate matches found
    """
    # Find memory directory
    memory_dir = None
    current = skill_path
    for _ in range(_MAX_MEMORY_SEARCH_LEVELS):
        parent = current.parent
        if (parent / "memory").exists():
            memory_dir = parent / "memory"
            break
        current = parent

    if not memory_dir or not memory_dir.exists():
        return 0

    # Get all .md files in memory/
    memory_files = list(memory_dir.glob("*.md"))
    if not memory_files:
        return 0

    # Extract content blocks from SKILL.md (paragraphs)
    skill_blocks = _extract_content_blocks(skill_content)

    # Check for duplicates
    duplicate_count = 0
    for memory_file in memory_files:
        try:
            memory_content = memory_file.read_text(encoding="utf-8")
            memory_blocks = _extract_content_blocks(memory_content)

            # Find common blocks (3+ lines matching)
            common_blocks = set(skill_blocks) & set(memory_blocks)
            if common_blocks:
                duplicate_count += len(common_blocks)
        except Exception:
            continue

    return duplicate_count


def _extract_content_blocks(content: str) -> list[str]:
    """Extract content blocks (paragraphs) from text.

    A content block is 3 or more consecutive non-empty lines.

    Args:
        content: Text content

    Returns:
        List of content blocks (as normalized strings)
    """
    lines = content.splitlines()
    blocks = []
    current_block = []

    for line in lines:
        stripped = line.strip()
        if stripped:
            current_block.append(stripped)
        else:
            if len(current_block) >= _MIN_BLOCK_LINES:
                # Normalize and store block
                block_key = "\n".join(current_block).lower()
                blocks.append(block_key)
            current_block = []

    # Don't forget the last block
    if len(current_block) >= _MIN_BLOCK_LINES:
        block_key = "\n".join(current_block).lower()
        blocks.append(block_key)

    return blocks


def _check_references(skill_path: Path, skill_content: str) -> list[str]:
    """Check that all references/ links exist.

    Args:
        skill_path: Path to the skill directory
        skill_content: Content of SKILL.md

    Returns:
        List of missing reference files
    """
    # Find all markdown link references: [text](references/something.md)
    pattern = r"\[[^\]]+\]\(references/([^)]+\.md)\)"
    matches = re.findall(pattern, skill_content)

    if not matches:
        return []

    references_dir = skill_path / "references"
    if not references_dir.exists():
        # All references are broken if directory doesn't exist
        return matches

    broken = []
    for filename in matches:
        ref_file = references_dir / filename
        if not ref_file.exists():
            broken.append(filename)

    return broken
