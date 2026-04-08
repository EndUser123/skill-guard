"""Tests for context size validation in skill-ship."""

# Import the actual implementation
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from validators.context_size import validate_context_size


class TestContextSizeValidation:
    """Test suite for context size validation."""

    def test_line_count_warning(self, tmp_path):
        """SKILL.md with 350 lines returns WARN."""
        skill_file = tmp_path / "SKILL.md"
        content = "\n".join([f"Line {i}" for i in range(350)])
        skill_file.write_text(content)

        result = validate_context_size(str(tmp_path))
        assert result.status == "warn"
        assert result.line_count == 350
        assert any("350 lines" in f for f in result.findings)

    def test_line_count_block(self, tmp_path):
        """SKILL.md with 550 lines returns FAIL."""
        skill_file = tmp_path / "SKILL.md"
        content = "\n".join([f"Line {i}" for i in range(550)])
        skill_file.write_text(content)

        result = validate_context_size(str(tmp_path))
        assert result.status == "fail"
        assert result.line_count == 550
        assert any("500 lines" in f for f in result.findings)

    def test_line_count_pass(self, tmp_path):
        """SKILL.md with 200 lines returns PASS."""
        skill_file = tmp_path / "SKILL.md"
        content = "\n".join([f"Line {i}" for i in range(200)])
        skill_file.write_text(content)

        result = validate_context_size(str(tmp_path))
        assert result.status == "pass"
        assert result.line_count == 200
        assert len(result.findings) == 0

    def test_missing_skill_file(self, tmp_path):
        """Non-existent SKILL.md returns FAIL."""
        # Test with a directory that doesn't have SKILL.md
        empty_dir = tmp_path / "empty_skill"
        empty_dir.mkdir()

        result = validate_context_size(str(empty_dir))
        assert result.status == "fail"
        assert any("not found" in f.lower() for f in result.findings)

    def test_duplicate_detection(self, tmp_path):
        """Duplicate detection doesn't crash - actual functionality requires memory/ dir."""
        skill_file = tmp_path / "SKILL.md"
        duplicate_content = "# Common Pattern\n\nThis is repeated content."
        skill_file.write_text(duplicate_content * 100)  # 100 lines

        result = validate_context_size(str(tmp_path))
        # Should at least not crash
        assert result.status in ["pass", "warn", "fail"]
        # No memory/ dir means no duplicates found
        assert result.duplicate_count == 0

    def test_reference_integrity_pass(self, tmp_path):
        """All references exist returns no warnings."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Test\n\nSee [reference](references/example.md)")

        # Create the referenced file
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        (refs_dir / "example.md").write_text("# Example")

        result = validate_context_size(str(tmp_path))
        assert len(result.broken_references) == 0

    def test_reference_integrity_missing(self, tmp_path):
        """Missing references are reported."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Test\n\nSee [missing](references/missing.md)")

        # Don't create the referenced file
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()

        result = validate_context_size(str(tmp_path))
        assert "missing.md" in result.broken_references

    def test_empty_skill_file(self, tmp_path):
        """Empty SKILL.md passes with 0 lines."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("")

        result = validate_context_size(str(tmp_path))
        assert result.status == "pass"
        assert result.line_count == 0

    def test_exactly_300_lines_boundary(self, tmp_path):
        """Exactly 300 lines should pass (boundary test)."""
        skill_file = tmp_path / "SKILL.md"
        content = "\n".join([f"Line {i}" for i in range(300)])
        skill_file.write_text(content)

        result = validate_context_size(str(tmp_path))
        # 300 is the threshold - should pass (not warn, only >300 warns)
        assert result.status == "pass"

    def test_exactly_500_lines_boundary(self, tmp_path):
        """Exactly 500 lines should warn (boundary test)."""
        skill_file = tmp_path / "SKILL.md"
        content = "\n".join([f"Line {i}" for i in range(500)])
        skill_file.write_text(content)

        result = validate_context_size(str(tmp_path))
        # 500 is the warn threshold - should warn (not fail, only >500 fails)
        assert result.status == "warn"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
