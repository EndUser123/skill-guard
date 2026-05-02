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
    """Tests documenting the current file structure issues."""

    @pytest.fixture
    def source_file(self):
        """Path to the skill_execution_state.py file."""
        return Path("P:/packages/skill-guard/src/skill_guard/skill_execution_state.py")

    @pytest.fixture
    def source_code(self, source_file):
        """Full source code of the file."""
        return source_file.read_text(encoding="utf-8")

    def test_file_has_over_1000_lines(self, source_file):
        """Characterization: File has over 1000 lines, indicating potential god object."""
        line_count = len(source_file.read_text(encoding="utf-8").splitlines())
        assert line_count > 1000, f"File has {line_count} lines, expected > 1000"

    def test_multiple_responsibility_clusters_exist(self, source_code):
        """Characterization: File contains multiple distinct responsibility clusters."""
        # Phase constants cluster
        phase_constants = re.search(
            r'_PHASE_PENDING\s*=\s*"pending"', source_code
        )
        # Terminal detection cluster
        terminal_detection = re.search(
            r'def detect_terminal_id', source_code
        )
        # Frontmatter loading cluster
        frontmatter_loading = re.search(
            r'def _load_skill_frontmatter', source_code
        )
        # State I/O cluster
        state_io = re.search(
            r'def _atomic_write_json', source_code
        )
        # Ledger integration cluster
        ledger_integration = re.search(
            r'def _get_ledger_module', source_code
        )
        # State update functions cluster
        state_updates = re.search(
            r'def set_skill_loaded', source_code
        )
        # Migration helpers cluster
        migration_helpers = re.search(
            r'def migrate_legacy_state', source_code
        )

        clusters = {
            "phase_constants": bool(phase_constants),
            "terminal_detection": bool(terminal_detection),
            "frontmatter_loading": bool(frontmatter_loading),
            "state_io": bool(state_io),
            "ledger_integration": bool(ledger_integration),
            "state_updates": bool(state_updates),
            "migration_helpers": bool(migration_helpers),
        }

        found_clusters = sum(clusters.values())
        assert found_clusters >= 5, (
            f"Expected at least 5 responsibility clusters, found {found_clusters}: {clusters}"
        )

    def test_responsibilities_not_separated_into_modules(self, source_file):
        """Characterization: All responsibilities live in single file, not separated modules."""
        # Parse the source to count top-level function definitions
        source_code = source_file.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        # Count function definitions at module level (not inside classes)
        module_level_functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.col_offset == 0
        ]

        # The file should have many functions if all responsibilities are in one place
        assert len(module_level_functions) >= 15, (
            f"File has only {len(module_level_functions)} top-level functions. "
            f"A god object with 20+ responsibilities would have significantly more."
        )

    def test_responsibility_clusters_not_documented_separately(self, source_code):
        """Characterization: Responsibilities are NOT separated by module boundaries."""
        # Check for module-level separation comments or section headers
        section_markers = [
            "TERMINAL DETECTION",
            "STATE MANAGEMENT",
            "FRONTMATTER",
            "LEDGER MODULE INTEGRATION",
            "MIGRATION HELPERS",
            "PHASE",
            "CONFIGURATION",
        ]

        found_markers = [marker for marker in section_markers if marker in source_code]

        # The file uses section headers as comments (indicating awareness of too many responsibilities)
        assert len(found_markers) >= 4, (
            f"File uses {len(found_markers)} section comment headers to organize "
            f"responsibilities that should be separate modules. "
            f"Found: {found_markers}"
        )

    def test_phase_constants_should_be_separate_module(self, source_code):
        """Characterization: Phase constants cluster exists and should be its own module."""
        # Phase constants pattern
        phase_pattern = re.search(
            r'_PHASE_PENDING\s*=\s*"pending".*VALID_TRANSITIONS.*DEFAULT_STALE_TIMEOUT',
            source_code,
            re.DOTALL
        )
        assert phase_pattern is not None, "Phase constants cluster not found"

    def test_terminal_detection_should_be_separate_module(self, source_code):
        """Characterization: Terminal detection should be its own module."""
        terminal_detect = re.search(r'def detect_terminal_id', source_code)
        assert terminal_detect is not None, "Terminal detection not found"

        # Should import from utils, but the function lives here
        import_in_function = re.search(
            r'from skill_guard\.utils\.terminal_detection import detect_terminal_id',
            source_code
        )
        assert import_in_function is not None, "Terminal detection imports from utils but function still lives here"

    def test_state_io_should_be_separate_module(self, source_code):
        """Characterization: State I/O operations should be their own module."""
        atomic_write = re.search(r'def _atomic_write_json', source_code)
        state_file_funcs = re.search(r'def _get_state_file', source_code)
        assert atomic_write is not None and state_file_funcs is not None, (
            "State I/O functions should be separate module"
        )

    def test_frontmatter_loading_should_be_separate_module(self, source_code):
        """Characterization: Frontmatter loading/validation should be its own module."""
        load_func = re.search(r'def _load_skill_frontmatter', source_code)
        validate_func = re.search(r'def _validate_skill_frontmatter', source_code)
        assert load_func is not None and validate_func is not None, (
            "Frontmatter functions should be separate module"
        )

    def test_ledger_integration_should_be_separate_module(self, source_code):
        """Characterization: Ledger module integration should be its own module."""
        ledger_func = re.search(r'def _get_ledger_module', source_code)
        assert ledger_func is not None, "Ledger integration should be separate module"

    def test_state_update_functions_should_be_separate_module(self, source_code):
        """Characterization: High-level state operations should be their own module."""
        state_ops = [
            "def set_skill_loaded",
            "def record_tool_use",
            "def transition_phase",
            "def read_pending_state",
            "def mark_first_tool_validated",
            "def update_workflow_stage",
            "def clear_state",
        ]
        for op in state_ops:
            assert re.search(op, source_code) is not None, f"{op} should be in separate module"

    def test_migration_helpers_should_be_separate_module(self, source_code):
        """Characterization: Migration helpers should be their own module."""
        migrate = re.search(r'def migrate_legacy_state', source_code)
        cleanup = re.search(r'def cleanup_stale_state_files', source_code)
        assert migrate is not None and cleanup is not None, (
            "Migration helpers should be separate module"
        )

    def test_legacy_cache_should_be_separate_module(self, source_code):
        """Characterization: Legacy metadata cache pattern should be its own module."""
        legacy_cache = re.search(r'_LEGACY_SKILL_METADATA_CACHE', source_code)
        get_cache_func = re.search(r'def _get_legacy_skill_metadata_cache', source_code)
        assert legacy_cache is not None and get_cache_func is not None, (
            "Legacy cache should be separate module"
        )