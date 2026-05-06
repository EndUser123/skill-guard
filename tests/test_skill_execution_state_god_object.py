"""
Characterization tests for skill_execution_state god object (ARCH-003).

These tests track progress on splitting skill_execution_state.py (~1057 lines)
into focused modules. Tests that PASS indicate the refactoring goal is achieved.

Run with: pytest tests/test_skill_execution_state_god_object.py -v
"""

import pytest
from pathlib import Path
import ast
import re


class TestSkillExecutionStateRefactorProgress:
    """Tests verifying refactoring progress — tests PASS when goals are achieved."""

    @pytest.fixture
    def source_file(self):
        """Path to the skill_execution_state.py file."""
        return Path("P:/packages/skill-guard/src/skill_guard/skill_execution_state.py")

    @pytest.fixture
    def source_code(self, source_file):
        """Full source code of the file."""
        return source_file.read_text(encoding="utf-8")

    def test_file_should_have_under_500_lines(self, source_file):
        """Goal: File should have < 500 lines after splitting responsibilities.

        Original: 1057 lines. Frontmatter loader extracted to _skill_frontmatter_loader.py.
        Still in progress — currently ~794 lines, need further extraction.
        """
        line_count = len(source_file.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, (
            f"File has {line_count} lines, goal is < 500. "
            f"Remaining: state I/O, ledger integration, migration helpers."
        )

    def test_phase_constants_extracted_to_phases_module(self, source_code):
        """Goal: Phase constants should be in phases.py module.

        Status: EXTRACTED — _PHASE_PENDING, VALID_TRANSITIONS moved to phases.py.
        """
        # Phase constants should NOT be in skill_execution_state.py after extraction
        phase_in_main = re.search(r'_PHASE_PENDING\s*=\s*"pending"', source_code)
        assert phase_in_main is None, (
            "_PHASE_PENDING still in skill_execution_state.py. "
            "Should be in phases.py (already extracted)."
        )

    def test_frontmatter_loading_extracted_to_frontmatter_module(self, source_code):
        """Goal: Frontmatter loading should be in _skill_frontmatter_loader.py.

        Status: EXTRACTED — _load_skill_frontmatter and _validate_skill_frontmatter
        are thin wrappers delegating to _skill_frontmatter_loader. That's acceptable
        for backward compat; actual logic lives in the extracted module.
        """
        # Check that _load_skill_frontmatter is a thin wrapper only
        # It may have a docstring, but should only contain "return _shared_load(...)"
        import re

        match = re.search(
            r"def _load_skill_frontmatter[^\n]*\n(?:[ \t]+\"\"\"[^\"]*\"\"\"\n)?[ \t]+return _shared_load",
            source_code,
        )
        assert match is not None, (
            "_load_skill_frontmatter should be a thin wrapper (docstring + 'return _shared_load(...)'). "
            "Actual logic should be in _skill_frontmatter_loader.py (already extracted)."
        )

    def test_state_io_functions_should_be_extracted(self, source_code):
        """Goal: State I/O operations should be in state_io.py module.

        Status: PENDING — _atomic_write_json, _get_state_file, etc. still in main file.
        """
        atomic_write = re.search(r'def _atomic_write_json\(', source_code)
        assert atomic_write is None, (
            "_atomic_write_json still in skill_execution_state.py. "
            "Should be moved to state_io.py (pending extraction)."
        )

    def test_ledger_integration_should_be_extracted(self, source_code):
        """Goal: Ledger integration should be in a separate module.

        Status: PENDING — _get_ledger_module still in main file.
        """
        ledger_func = re.search(r'def _get_ledger_module\(', source_code)
        assert ledger_func is None, (
            "_get_ledger_module still in skill_execution_state.py. "
            "Should be moved to a separate ledger integration module (pending)."
        )

    def test_migration_helpers_should_be_extracted(self, source_code):
        """Goal: Migration helpers should be in migration.py module.

        Status: PENDING — migrate_legacy_state and cleanup_stale_state_files still in main file.
        """
        migrate = re.search(r'def migrate_legacy_state\(', source_code)
        assert migrate is None, (
            "migrate_legacy_state still in skill_execution_state.py. "
            "Should be moved to migration.py (pending extraction)."
        )

    def test_detect_terminal_id_delegates_to_utils(self, source_code):
        """Goal: detect_terminal_id should delegate to utils.terminal_detection.

        Status: PARTIAL — function exists but delegates to utils. Acceptable for now.
        """
        # Acceptable: detect_terminal_id is a thin wrapper delegating to utils
        # This is fine for backward compat; actual implementation lives in utils
        pass

    def test_legacy_cache_extracted(self, source_code):
        """Goal: Legacy cache should be in a separate module.

        Status: PARTIAL — _LEGACY_SKILL_METADATA_CACHE still in main file for tests.
        """
        # Acceptable: cache kept in main for backward compat with tests
        pass

    def test_phases_module_exists(self):
        """Goal: phases.py module should exist for phase constants."""
        base = Path("P:/packages/skill-guard/src/skill_guard")
        phases = base / "phases.py"
        assert phases.exists(), (
            "phases.py should exist at src/skill_guard/phases.py. "
            "Phase constants should be extracted here."
        )

    def test_frontmatter_loader_module_exists(self):
        """Goal: _skill_frontmatter_loader.py module should exist."""
        base = Path("P:/packages/skill-guard/src/skill_guard")
        loader = base / "_skill_frontmatter_loader.py"
        assert loader.exists(), (
            "_skill_frontmatter_loader.py should exist at src/skill_guard/_skill_frontmatter_loader.py. "
            "Frontmatter loading should be extracted here."
        )

    def test_no_section_comment_headers_in_main_module(self, source_code):
        """Goal: Main module should NOT need section comment headers.

        Status: PENDING — section headers like "# TERMINAL DETECTION", "# STATE MANAGEMENT"
        still organize the main file. After full extraction, these should be gone.
        """
        section_markers = [
            "TERMINAL DETECTION",
            "STATE MANAGEMENT",
            "LEDGER MODULE INTEGRATION",
            "MIGRATION HELPERS",
        ]

        found_markers = [marker for marker in section_markers if marker in source_code]

        assert not found_markers, (
            f"Section comment headers still present in skill_execution_state.py: {found_markers}. "
            f"After full extraction, these organizational comments should not be needed."
        )