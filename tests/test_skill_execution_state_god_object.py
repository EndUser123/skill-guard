"""
Characterization tests for skill_execution_state god object (ARCH-003).

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
The file has 1057 lines with 20+ responsibilities that should be separated.

Run with: pytest tests/test_skill_execution_state_god_object.py -v
"""

import pytest
from pathlib import Path
import ast
import re


class TestSkillExecutionStateGodObject:
    """Tests verifying the DESIRED state after refactoring - tests should FAIL now."""

    @pytest.fixture
    def source_file(self):
        """Path to the skill_execution_state.py file."""
        return Path("P:/packages/skill-guard/src/skill_guard/skill_execution_state.py")

    @pytest.fixture
    def source_code(self, source_file):
        """Full source code of the file."""
        return source_file.read_text(encoding="utf-8")

    def test_file_should_have_under_500_lines(self, source_file):
        """REFACTOR GOAL: File should have < 500 lines after splitting responsibilities.

        Currently has 1057 lines - this test FAILS showing refactoring is needed.
        """
        line_count = len(source_file.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, (
            f"File has {line_count} lines, refactoring should reduce to < 500. "
            f"Phase constants, terminal detection, frontmatter, state I/O, ledger "
            f"integration, and migration helpers should be separate modules."
        )

    def test_main_module_should_have_fewer_than_10_top_level_functions(self, source_file):
        """REFACTOR GOAL: Main module should have < 10 top-level functions after splitting.

        Currently has many functions handling too many responsibilities.
        This test FAILS showing refactoring is needed.
        """
        source_code = source_file.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        # Count function definitions at module level (not inside classes)
        module_level_functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.col_offset == 0
        ]

        assert len(module_level_functions) < 10, (
            f"File has {len(module_level_functions)} top-level functions. "
            f"After refactoring, should have < 10 (main module only coordinates submodules)."
        )

    def test_phase_constants_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Phase constants should be in src/skill_guard/phases.py

        Currently phase constants (_PHASE_PENDING, VALID_TRANSITIONS, etc.) live
        in skill_execution_state.py. After refactoring, they should be in a
        separate module like phases.py.

        This test FAILS because the constants still live in the main file.
        """
        # Phase constants should NOT be in skill_execution_state.py after refactoring
        phase_in_main = re.search(r'_PHASE_PENDING\s*=\s*"pending"', source_code)
        assert phase_in_main is None, (
            "Phase constants (_PHASE_PENDING, etc.) still in skill_execution_state.py. "
            "They should be moved to src/skill_guard/phases.py"
        )

    def test_terminal_detection_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Terminal detection should only delegate, not implement.

        Currently detect_terminal_id() is implemented here but also imports from utils.
        After refactoring, this module should only delegate to utils.terminal_detection.
        """
        # detect_terminal_id should be removed from this module (only in utils)
        detect_in_main = re.search(r'^def detect_terminal_id', source_code, re.MULTILINE)
        assert detect_in_main is None, (
            "detect_terminal_id() still implemented in skill_execution_state.py. "
            "Should only delegate to utils.terminal_detection module."
        )

    def test_frontmatter_loading_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Frontmatter loading should be in frontmatter.py module.

        Currently _load_skill_frontmatter and _validate_skill_frontmatter are here.
        After refactoring, should be in src/skill_guard/frontmatter.py.
        """
        load_func = re.search(r'def _load_skill_frontmatter', source_code)
        assert load_func is None, (
            "_load_skill_frontmatter still in skill_execution_state.py. "
            "Should be moved to src/skill_guard/frontmatter.py"
        )

    def test_state_io_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: State I/O operations should be in state_io.py module.

        Currently _atomic_write_json, _get_state_file, etc. are here.
        After refactoring, should be in src/skill_guard/state_io.py.
        """
        atomic_write = re.search(r'def _atomic_write_json', source_code)
        assert atomic_write is None, (
            "_atomic_write_json and state I/O functions still in skill_execution_state.py. "
            "Should be moved to src/skill_guard/state_io.py"
        )

    def test_ledger_integration_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Ledger integration should be in ledger.py module.

        Currently _get_ledger_module is here. After refactoring, should be
        in src/skill_guard/ledger.py or similar.
        """
        ledger_func = re.search(r'def _get_ledger_module', source_code)
        assert ledger_func is None, (
            "_get_ledger_module still in skill_execution_state.py. "
            "Should be moved to a separate ledger integration module."
        )

    def test_migration_helpers_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Migration helpers should be in migration.py module.

        Currently migrate_legacy_state and cleanup_stale_state_files are here.
        After refactoring, should be in src/skill_guard/migration.py.
        """
        migrate = re.search(r'def migrate_legacy_state', source_code)
        assert migrate is None, (
            "migrate_legacy_state still in skill_execution_state.py. "
            "Should be moved to src/skill_guard/migration.py"
        )

    def test_separate_module_files_should_exist(self):
        """REFACTOR GOAL: Separate module files should exist for each responsibility.

        After refactoring, these files should exist:
        - phases.py (phase constants)
        - frontmatter.py (frontmatter loading/validation)
        - state_io.py (state file I/O)
        - ledger.py (ledger integration)

        This test FAILS because these files don't exist yet.
        """
        base = Path("P:/packages/skill-guard/src/skill_guard")
        expected_modules = ["phases.py", "frontmatter.py", "state_io.py", "ledger.py"]

        missing = [m for m in expected_modules if not (base / m).exists()]

        assert not missing, (
            f"Missing separate module files: {missing}. "
            f"Refactoring should split skill_execution_state.py into these modules."
        )

    def test_legacy_cache_should_be_in_separate_module(self, source_code):
        """REFACTOR GOAL: Legacy cache pattern should be in cache.py module.

        Currently _LEGACY_SKILL_METADATA_CACHE and _get_legacy_skill_metadata_cache
        are here. After refactoring, should be in src/skill_guard/cache.py.
        """
        legacy_cache = re.search(r'_LEGACY_SKILL_METADATA_CACHE', source_code)
        assert legacy_cache is None, (
            "_LEGACY_SKILL_METADATA_CACHE still in skill_execution_state.py. "
            "Should be moved to src/skill_guard/cache.py"
        )

    def test_no_section_comment_headers_in_main_module(self, source_code):
        """REFACTOR GOAL: Main module should NOT need section comment headers.

        Currently the file uses comments like "# TERMINAL DETECTION", "# STATE MANAGEMENT"
        to organize responsibilities within a single file. After proper refactoring
        into separate modules, these section headers should not be needed in the main module.
        """
        section_markers = [
            "TERMINAL DETECTION",
            "STATE MANAGEMENT",
            "FRONTMATTER",
            "LEDGER MODULE INTEGRATION",
            "MIGRATION HELPERS",
        ]

        found_markers = [marker for marker in section_markers if marker in source_code]

        assert not found_markers, (
            f"Section comment headers still present in skill_execution_state.py: {found_markers}. "
            f"These organizational comments indicate responsibilities that should be "
            f"in separate modules, not commented sections in a single god object."
        )