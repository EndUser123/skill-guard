#!/usr/bin/env python3
"""
PreToolUse Hook: Import Deletion Guard

Blocks removal of Python import statements unless the imported symbol
was searched for in the current turn.

Prevents the HyDEGenerator incident: LLM deleted import because file search
failed, but symbol actually existed at a different path.

Configuration:
    IMPORT_DELETION_GUARD_ENABLED=true to enable (default)
    IMPORT_DELETION_GUARD_VERBOSE=true for detailed logging

Bypass: Add --allow-import-removal to user message
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Add hooks directory to path for imports (hardcoded — __file__ resolves to plugin dir)
HOOKS_DIR = Path(r"P:/.claude/hooks")
sys.path.insert(0, str(HOOKS_DIR))

# Configuration
ENABLED = os.environ.get("IMPORT_DELETION_GUARD_ENABLED", "true").lower() in ("1", "true", "yes")
VERBOSE = os.environ.get("IMPORT_DELETION_GUARD_VERBOSE", "false").lower() in ("1", "true", "yes")

# Try to import evidence store
try:
    from turn_scoped_evidence import load_turn_scoped_events
    EVIDENCE_AVAILABLE = True
except Exception:
    load_turn_scoped_events = None  # type: ignore[assignment]
    EVIDENCE_AVAILABLE = False

# Patterns for import parsing (with DOTALL for multiline imports)
FROM_IMPORT_RE = re.compile(
    r"^\s*from\s+\S+\s+import\s+(.+)",
    re.MULTILINE | re.DOTALL
)

IMPORT_RE = re.compile(
    r"^\s*import\s+(.+)",
    re.MULTILINE | re.DOTALL
)


def extract_import_symbols(text: str) -> set[str]:
    """Extract symbol names from import statements in text.

    Handles:
    - from module import Foo
    - from module import Foo, Bar
    - from module import (Foo, Bar) [multiline]
    - import module
    - import module as alias
    - import os, sys, re (multiple on one line)

    Returns:
        Set of symbol names (not module paths, not aliases)
    """
    symbols = set()

    # Process 'from ... import' statements
    for match in FROM_IMPORT_RE.finditer(text):
        import_clause = match.group(1)
        # Strip comments
        import_clause = re.sub(r"#.*", "", import_clause)
        # Strip parentheses and normalize whitespace
        import_clause = re.sub(r"[()]", " ", import_clause)
        import_clause = re.sub(r"\s+", " ", import_clause).strip()

        # Split by comma and extract symbol names
        for part in import_clause.split(","):
            part = part.strip()
            if not part:
                continue
            # Extract symbol name (handle 'symbol as alias')
            symbol = part.split(" as ")[0].strip()
            if symbol:
                symbols.add(symbol)

    # Process 'import ...' statements
    for match in IMPORT_RE.finditer(text):
        module_spec = match.group(1)
        # Strip comments
        module_spec = re.sub(r"#.*", "", module_spec).strip()

        # Handle multiple imports on one line: import os, sys, re
        # Also handle: import os as my_os
        for part in module_spec.split(","):
            part = part.strip()
            if not part:
                continue
            # Extract module name (handle 'module as alias')
            module = part.split(" as ")[0].strip()
            if module:
                # For 'import os.path', we want 'os.path'
                # For 'import os', we want 'os'
                symbols.add(module)

    return symbols


def extract_removed_symbols(old_string: str, new_string: str) -> set[str]:
    """Find symbols present in old_string imports but absent in new_string imports.

    Returns:
        Set of symbol names that were removed
    """
    old_imports = extract_import_symbols(old_string)
    new_imports = extract_import_symbols(new_string)
    return old_imports - new_imports


def has_symbol_search_this_turn(symbol: str, tool_events: list[dict]) -> bool:
    """Check if a grep for the symbol was executed this turn.

    Args:
        symbol: Symbol name to search for
        tool_events: List of tool events from this turn

    Returns:
        True if a grep for this symbol was found
    """
    if not tool_events:
        return False

    symbol_lower = symbol.lower()

    def _command_mentions_symbol(command: str) -> bool:
        command_lower = command.lower()
        if symbol_lower not in command_lower:
            return False
        search_markers = (
            "grep",
            " rg ",
            " rg\t",
            "rg ",
            "select-string",
            "findstr",
            "sls ",
        )
        return any(marker in command_lower for marker in search_markers)

    for event in tool_events:
        tool_name = event.get("name") or event.get("tool_name", "")

        # Check Grep tool
        if tool_name == "Grep":
            pattern = event.get("pattern") or ""
            if symbol_lower in pattern.lower():
                return True

        # Check Bash with grep command
        elif tool_name == "Bash":
            command = event.get("command", "")
            if _command_mentions_symbol(command):
                return True

    return False


def extract_module_name(import_line: str) -> str | None:
    """Extract the module name from an import statement.

    'from .tracing import X' → 'tracing'
    'from .sub.tracing import X' → 'sub.tracing'
    'from collections import X' → 'collections'
    'import os' → 'os'
    """
    match = re.match(r'^\s*from\s+\.+([.\w]*)\s+import', import_line)
    if match:
        return match.group(1).lstrip('.') or None

    match = re.match(r'^\s*from\s+([\w.]+)\s+import', import_line)
    if match:
        return match.group(1)

    match = re.match(r'^\s*import\s+([\w.]+)', import_line)
    if match:
        return match.group(1)

    return None


def has_investigation_evidence(
    old_string: str,
    removed_symbols: set[str],
    file_path: str,
    tool_events: list[dict],
) -> bool:
    """Check if the turn contains evidence of investigating the imported module.

    Evidence:
    - Read tool targeting a path containing the module name
    - Bash tool with git log/status/diff/blame for the module path
    - Grep tool searching for any removed symbol or module name
    - Bash tool with grep/findstr for any removed symbol or module name
    """
    if not tool_events:
        return False

    module_names: set[str] = set()
    for line in old_string.split("\n"):
        name = extract_module_name(line)
        if name:
            module_names.add(name)
            if "." in name:
                module_names.add(name.split(".")[-1])

    if not module_names and not removed_symbols:
        return False

    for event in tool_events:
        tool_name = event.get("name") or event.get("tool_name", "")

        if tool_name == "Read":
            read_path = (event.get("file_path") or "").lower()
            for mod in module_names:
                if mod.lower() in read_path:
                    return True

        elif tool_name == "Grep":
            pattern = (event.get("pattern") or "").lower()
            if any(s.lower() in pattern for s in removed_symbols):
                return True
            for mod in module_names:
                if mod.lower() in pattern:
                    return True

        elif tool_name == "Bash":
            command = (event.get("command") or "").lower()
            git_markers = ("git log", "git status", "git diff", "git show", "git blame")
            for mod in module_names:
                if mod.lower() in command and any(m in command for m in git_markers):
                    return True
            search_markers = ("grep", " rg ", " rg\t", "rg ", "select-string", "findstr", "sls ")
            if any(m in command for m in search_markers):
                for sym in removed_symbols:
                    if sym.lower() in command:
                        return True
                for mod in module_names:
                    if mod.lower() in command:
                        return True

    return False


def load_this_turn_events(session_id: str, terminal_id: str) -> list[dict] | None:
    """Load tool events for the current turn.

    Returns:
        List of events, or None if evidence system unavailable
    """
    if not EVIDENCE_AVAILABLE or load_turn_scoped_events is None:
        return None

    if not session_id:
        return None

    try:
        events = load_turn_scoped_events(
            session_id=session_id,
            terminal_id=terminal_id,
            limit=200,
        )
        return events
    except Exception:
        return None


def has_bypass_flag(user_message: str) -> bool:
    """Check if user message contains bypass flag."""
    return "--allow-import-removal" in user_message


def _iter_candidate_edits(tool_name: str, tool_input: dict) -> list[tuple[str, str, str]]:
    """Return (file_path, old_content, new_content) tuples to inspect."""
    candidates: list[tuple[str, str, str]] = []

    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        if not isinstance(edits, list):
            return candidates
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            file_path = str(edit.get("file_path", ""))
            if not file_path.endswith(".py"):
                continue
            old_string = str(edit.get("old_string", ""))
            new_string = str(edit.get("new_string", ""))
            if old_string:
                candidates.append((file_path, old_string, new_string))
        return candidates

    file_path = str(tool_input.get("file_path", ""))
    if not file_path.endswith(".py"):
        return candidates

    if tool_name == "Edit":
        old_string = str(tool_input.get("old_string", ""))
        new_string = str(tool_input.get("new_string", ""))
        if old_string:
            candidates.append((file_path, old_string, new_string))
        return candidates

    if tool_name == "Write":
        proposed_content = str(tool_input.get("content", ""))
        if not proposed_content:
            return candidates

        existing_path = Path(file_path)
        if not existing_path.exists():
            return candidates

        try:
            existing_content = existing_path.read_text(encoding="utf-8")
        except OSError:
            return candidates

        candidates.append((file_path, existing_content, proposed_content))
        return candidates

    return candidates


def evaluate(data: dict) -> dict | None:
    """Core logic shared by run() and main(). Returns block dict or None (allow)."""
    if not ENABLED:
        return None

    tool_name = data.get("tool_name", "")
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        return None

    tool_input = data.get("tool_input", {})

    user_message = data.get("user_message", "")
    if has_bypass_flag(user_message):
        return None

    session_id = data.get("session_id", "")
    terminal_id = data.get("terminal_id", "")

    tool_events = load_this_turn_events(session_id, terminal_id)
    if tool_events is None:
        # Fail closed: block import deletions when evidence store is unavailable
        for file_path, old_string, new_string in _iter_candidate_edits(tool_name, tool_input):
            removed_symbols = extract_removed_symbols(old_string, new_string)
            if not removed_symbols:
                continue
            symbols_str = ", ".join(sorted(removed_symbols))
            reason = f"""⛔ IMPORT DELETION WITHOUT EVIDENCE (session unavailable)

You are removing the import of: {symbols_str}
From: {file_path}

The evidence store is unavailable for this session, so prior investigation
cannot be verified. Before removing this import, search for the symbol:
  grep -r "{sorted(removed_symbols)[0]}" --include="*.py" P:/

If the search confirms the symbol is genuinely absent everywhere, proceed.

Bypass: Add --allow-import-removal to your message."""
            return {"continue": False, "reason": reason}
        return None

    for file_path, old_string, new_string in _iter_candidate_edits(tool_name, tool_input):
        removed_symbols = extract_removed_symbols(old_string, new_string)
        if not removed_symbols:
            continue

        # Broader investigation check: Read of module, git log, or grep
        if has_investigation_evidence(old_string, removed_symbols, file_path, tool_events):
            continue

        unsymbols = sorted(removed_symbols)
        symbols_without_search = [s for s in unsymbols if not has_symbol_search_this_turn(s, tool_events)]
        if not symbols_without_search:
            continue  # All symbols were searched — allow this edit

        symbols_str = ", ".join(symbols_without_search)
        reason = f"""⛔ IMPORT DELETION WITHOUT SYMBOL SEARCH

You are removing the import of: {symbols_str}
From: {file_path}

Before removing this import, search for the symbol across the codebase:
  grep -r "{symbols_without_search[0]}" --include="*.py" P:/

The import path may be wrong (file at wrong location) without the symbol itself
being absent. Removing the import silently deletes functionality.

If the search confirms the symbol is genuinely absent everywhere, proceed.

Bypass: Add --allow-import-removal to your message."""

        return {"continue": False, "reason": reason}

    return None


def run(data: dict) -> dict | None:
    """In-process entry point for PreToolUse router."""
    return evaluate(data)


def main() -> int:
    """Subprocess entry point."""
    try:
        input_text = sys.stdin.read().strip()
        if not input_text:
            print(json.dumps({"continue": True}))
            return 0
        data = json.loads(input_text)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"continue": True}))
        return 0

    result = evaluate(data)
    if result and not result.get("continue", True):
        print(json.dumps(result))
        return 2

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
