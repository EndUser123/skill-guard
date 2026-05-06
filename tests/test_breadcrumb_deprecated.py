"""Tests for INVARIANT 5: breadcrumbs are NOT contract authority."""

from __future__ import annotations

import pytest


class TestBreadcrumbDeprecation:
    """
    INVARIANT 5 (breadcrumbs NOT contract authority) tests.

    Fact: Breadcrumbs are deprecated for contract enforcement. They remain
    for non-contract workflows (manual sessions, ad-hoc exploration) but
    have no enforcement role in the execution contract runtime.
    """

    def test_breadcrumb_module_not_imported_by_execution_hooks(self):
        """execution_hooks.py does not import from skill_guard.breadcrumb."""
        import ast
        from pathlib import Path

        hooks_path = Path("P:/packages/skill-guard/src/skill_guard/execution_hooks.py")
        source = hooks_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        breadcrumb_imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "breadcrumb" in node.module:
                        breadcrumb_imports.append(node.module)

        assert len(breadcrumb_imports) == 0, (
            f"execution_hooks.py must not import breadcrumb modules: {breadcrumb_imports}"
        )

    def test_breadcrumb_init_docstring_deprecated(self):
        """breadcrumb/__init__.py docstring must state deprecation for enforcement."""
        from skill_guard.breadcrumb import __doc__

        assert __doc__ is not None
        assert "DEPRECATED" in __doc__ or "deprecated" in __doc__.lower(), (
            "breadcrumb/__init__.py must document its deprecation for contract enforcement"
        )