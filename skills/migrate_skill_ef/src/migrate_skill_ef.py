#!/usr/bin/env python3
"""
Migration utility to create evidence-first (-ef) skill variants.

Creates full, coherent, runnable `*-ef` skill directories non-destructively,
wired to the shared enforce layer. Only two outcomes: complete success or
clean abort with a diagnostic — no stubs, no partial migrations.

Usage:
    python tools/migrate_to_ef.py --base refactor --dry-run
    python tools/migrate_to_ef.py --base refactor
    python tools/migrate_to_ef.py --base planning --target planning-ef
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------
# Layout constants
# -----------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]  # tools/ -> cc-skills-sdlc
SKILLS_DIR = _ROOT / "skills"
ENFORCE_DIR = _ROOT / "enforce"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# -----------------------------------------------------------------------
# Layout validation
# -----------------------------------------------------------------------

def validate_layout() -> list[str]:
    """Check that the expected skill/enforcement layout is present."""
    errors: list[str] = []
    if not ENFORCE_DIR.is_dir():
        errors.append(f"enforce/ not found at {ENFORCE_DIR}")
    if not (ENFORCE_DIR / "stop_gate.py").is_file():
        errors.append("enforce/stop_gate.py missing")
    if not (ENFORCE_DIR / "configs" / "__init__.py").is_file():
        errors.append("enforce/configs/__init__.py missing")
    return errors


# -----------------------------------------------------------------------
# Source resolution
# -----------------------------------------------------------------------

def resolve_source(base: str, source_path: str | None) -> Path | None:
    """Resolve source skill path. Returns None if not found."""
    if source_path:
        p = Path(source_path)
        if p.is_dir():
            return p
        return None
    candidates = [
        SKILLS_DIR / base,
        SKILLS_DIR / f"{base}_v3.0",
        SKILLS_DIR / f"{base}_v4.0",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def resolve_target(target: str | None, base: str) -> Path:
    """Default target is f'{base}-ef'."""
    name = target if target else f"{base}-ef"
    return SKILLS_DIR / name


# -----------------------------------------------------------------------
# Source skill structure analysis
# -----------------------------------------------------------------------

def read_frontmatter(skill_dir: Path) -> dict[str, Any]:
    """Parse YAML frontmatter block from SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    in_fm = False
    fm_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
            else:
                break  # end of frontmatter
            continue
        if in_fm:
            fm_lines.append(line)

    result: dict[str, Any] = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip().strip('"').strip("'")

    return result


def read_workflow_steps(skill_dir: Path) -> list[str]:
    """Extract workflow_steps list from SKILL.md body."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return []

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    steps: list[str] = []

    # Match "- STEP_NAME" at the start of a line (common YAML list format)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- [") and not stripped.startswith("- [x]"):
            step = stripped[2:].strip()
            if step and step.isupper() or re.match(r"^\d+\.", step):
                steps.append(step)

    return steps


def check_source_structure(source_dir: Path | None) -> tuple[bool, str, dict[str, Any]]:
    """Verify a source skill has enough structure for a real migration.

    Returns (can_migrate, reason, frontmatter_dict).
    - can_migrate=True: skill has SKILL.md with real content
    - can_migrate=False: reason explains why migration was refused
    """
    if not source_dir:
        return False, "source skill directory not found", {}

    skill_md = source_dir / "SKILL.md"
    if not skill_md.is_file():
        return False, f"SKILL.md not found in {source_dir}", {}

    fm = read_frontmatter(source_dir)
    body_text = skill_md.read_text(encoding="utf-8", errors="replace")

    # Must have at minimum: a name and non-trivial body
    name = fm.get("name", "")
    if not name:
        return False, f"SKILL.md in {source_dir} has no 'name' field", fm

    body_lines = [
        l for l in body_text.splitlines()
        if l.strip() and not l.strip().startswith("---")
    ]
    # frontmatter overhead (~15 lines) + some real content
    if len(body_lines) < 20:
        return False, (
            f"SKILL.md in {source_dir.name} is too thin for safe migration "
            f"(only ~{len(body_lines)} non-frontmatter lines). "
            "A runnable skill needs substantive body content."
        ), fm

    return True, "", fm


# -----------------------------------------------------------------------
# Phase derivation
# -----------------------------------------------------------------------

def derive_phases_from_source(source_dir: Path | None, target_name: str) -> list[dict[str, Any]]:
    """Derive real enforce phases from source skill structure.

    Phases are based on the source skill's workflow_steps or a sensible
    default. All phases are advisory — evidence must be wired separately.
    """
    steps = read_workflow_steps(source_dir) if source_dir else []

    if steps:
        return [
            {
                "name": step.lower().replace("_", "_"),
                "gate_type": "advisory",
                "evidence": {"type": "ledger_only"},
            }
            for step in steps
        ]

    # Safe default phase for skills without explicit workflow_steps
    return [
        {
            "name": "plan_and_execute",
            "gate_type": "advisory",
            "evidence": {"type": "ledger_only"},
        },
    ]


# -----------------------------------------------------------------------
# Config registration
# -----------------------------------------------------------------------

def register_config(skill_id: str, phases: list[dict[str, Any]]) -> tuple[bool, str]:
    """Add a real config entry to enforce/configs/__init__.py.

    Returns (was_new, message).
    """
    if str(ENFORCE_DIR.parent) not in sys.path:
        sys.path.insert(0, str(ENFORCE_DIR.parent))

    from enforce.configs import ENFORCE_CONFIGS

    if skill_id in ENFORCE_CONFIGS:
        return False, f"config for '{skill_id}' already exists"

    # Register in-memory
    ENFORCE_CONFIGS[skill_id] = phases

    # Persist to file
    config_path = ENFORCE_DIR / "configs" / "__init__.py"
    lines = config_path.read_text(encoding="utf-8").splitlines()

    insert_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('"go_v3.0"'):
            insert_idx = i + 1
            break

    if insert_idx is None:
        return False, "could not find ENFORCE_CONFIGS insertion point"

    indent = "    "
    new_lines = [
        f"{indent}# Entry created by migrate_to_ef.py",
        f'{indent}"{skill_id}": {phases},',
    ]
    lines = lines[:insert_idx] + new_lines + lines[insert_idx:]
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return True, f"registered config for '{skill_id}' with {_plural(len(phases), 'phase')}"


# -----------------------------------------------------------------------
# SKILL.md generation
# -----------------------------------------------------------------------

def _build_ef_header(target_name: str, old_name: str) -> str:
    """Build the evidence-first section header using plain concatenation."""
    return (
        "\n"
        "---\n"
        "\n"
        "# /" + target_name + " — Evidence-First Variant\n"
        "\n"
        "## What changed from " + old_name + "\n"
        "\n"
        "`-ef` is the canonical naming format for evidence-first enforced skills.\n"
        "Phase gates are managed by the shared `enforce/` layer.\n"
        "\n"
        "Evidence checked via "
        "`~/.claude/.state/enforce/" + target_name + "/{TERMINAL_ID}/phase-ledger.json`.\n"
        "\n"
        "---\n"
    )


def _build_stop_hook_block(target_name: str) -> str:
    """Build the Stop hook YAML block using plain concatenation."""
    hook_lines = [
        "\nhooks:\n",
        "  Stop:\n",
        '    - matcher: ".*"\n',
        "      hooks:\n",
        '        - type: command\n',
        "          command: \"python \\\"$CLAUDE_PLUGIN_ROOT\\\"/skills/"
        + target_name
        + "/hooks/Stop_enforce_gate.py\"\n",
        '          description: "Verify phase gates via shared enforce layer"\n',
    ]
    return "".join(hook_lines)


def generate_skill_md(source_dir: Path | None, target_name: str, base_name: str) -> str:
    """Generate a coherent SKILL.md for the new -ef variant.

    Preserves the source body but updates frontmatter:
    - name -> target_name
    - version -> 1.0.0
    - enforcement -> strict
    - triggers rewritten to target name
    - Stop hook registered
    """
    old_name = base_name
    source_md = source_dir / "SKILL.md" if source_dir else None

    if source_md and source_md.is_file():
        text = source_md.read_text(encoding="utf-8", errors="replace")

        # Find frontmatter
        fm_start = text.find("---")
        fm_end = text.find("---", fm_start + 3) if fm_start != -1 else -1

        if fm_start != -1 and fm_end != -1:
            fm_text = text[fm_start:fm_end + 3]

            # Replace name and version
            fm_text = fm_text.replace(f"name: {old_name}", f"name: {target_name}")
            for old_n in [f"name: {old_name}_v3.0", f"name: {old_name}_v4.0"]:
                fm_text = fm_text.replace(old_n, f"name: {target_name}")
            if f"name: go" in fm_text:
                fm_text = fm_text.replace("name: go", f"name: {target_name}")

            # Version reset
            fm_text = re.sub(r"^version: .+$", "version: 1.0.0", fm_text, flags=re.MULTILINE)

            # Enforcement upgrade
            fm_text = re.sub(
                r"^enforcement: .+$", "enforcement: strict", fm_text, flags=re.MULTILINE
            )

            # Rewrite triggers
            fm_text = re.sub(
                r"(?<!/)/" + re.escape(old_name) + r"\b",
                f"/{target_name}",
                fm_text,
            )

            # Add -ef Stop hook if not already present
            if "Stop_enforce_gate" not in fm_text:
                fm_text += _build_stop_hook_block(target_name)

            # Separate frontmatter from body
            body = text[fm_end + 3:]

            return fm_text + _build_ef_header(target_name, old_name) + body

    # Fallback for bare source
    cmd = ('python \\"$CLAUDE_PLUGIN_ROOT\\"/skills/' + target_name
           + '/hooks/Stop_enforce_gate.py')
    return (
        "---\n"
        "name: " + target_name + "\n"
        "version: 1.0.0\n"
        "description: Evidence-first variant of " + old_name + ". Uses the shared enforce layer.\n"
        "enforcement: strict\n"
        "status: stable\n"
        "hooks:\n"
        "  Stop:\n"
        '    - matcher: ".*"\n'
        "      hooks:\n"
        '        - type: command\n'
        "          command: \"" + cmd + "\"\n"
        '          description: "Verify phase gates via shared enforce layer"\n'
        "---\n"
        "\n"
        "# /" + target_name + " — Evidence-First Variant\n"
        "\n"
        "Evidence-first skill variant. Uses the shared enforce layer for phase gate tracking.\n"
    )


def generate_stop_hook(target_name: str) -> str:
    """Generate the Stop_enforce_gate.py hook."""
    lines = [
        "#!/usr/bin/env python3",
        '"""',
        f"Stop hook for /{target_name} — shared enforce layer.",
        '"""',
        "",
        "import os",
        "import sys",
        "from pathlib import Path",
        "",
        "_ROOT = Path(__file__).resolve().parents[3]",
        'if str(_ROOT) not in sys.path:',
        '    sys.path.insert(0, str(_ROOT))',
        "",
        "from enforce.stop_gate import load_config_for_skill, evaluate_gates",
        "",
        "",
        "def main() -> None:",
        f'    skill_id = "{target_name}"',
        "    try:",
        "        config = load_config_for_skill(skill_id)",
        "    except KeyError:",
        '        print("ERROR: no enforce config for " + skill_id, file=sys.stderr)',
        "        sys.exit(2)",
        "",
        "    exit_code, message = evaluate_gates(skill_id, config, os.environ)",
        "    if message:",
        "        print(message, file=sys.stderr)",
        "    sys.exit(exit_code)",
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------
# Dry-run reporter
# -----------------------------------------------------------------------

def report_dry_run(
    base: str,
    target_name: str,
    source_path: Path | None,
    target_path: Path,
    config_status: str,
    phases: list[dict[str, Any]],
    blockers: list[str],
) -> None:
    print("=" * 60)
    print("DRY RUN — no filesystem changes made")
    print("=" * 60)
    print(f"  Source skill : {source_path or '(not found)'}")
    print(f"  Target skill : {target_path}")
    print(f"  Config entry : {config_status}")
    if phases:
        print(f"  Phases       : {_plural(len(phases), 'phase')} (all advisory)")
    print()
    if blockers:
        print("  BLOCKERS:")
        for b in blockers:
            print(f"    - {b}")
    else:
        print("  Files to CREATE:")
        print(f"    {target_path}/")
        print(f"    {target_path}/hooks/")
        print(f"    {target_path}/SKILL.md  (source body preserved + -ef updates)")
        print(f"    {target_path}/hooks/Stop_enforce_gate.py")


# -----------------------------------------------------------------------
# Apply (partial artifacts cleaned up on failure)
# -----------------------------------------------------------------------

def apply(
    base: str,
    target_name: str,
    source_path: Path | None,
    target_path: Path,
    force: bool,
    phases: list[dict[str, Any]],
) -> None:
    """Create the new -ef skill variant. Cleans up on failure."""
    target_path.mkdir(parents=True, exist_ok=force)
    hooks_dir = target_path / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    created_files: list[Path] = []

    try:
        skill_md_path = target_path / "SKILL.md"
        skill_md_path.write_text(
            generate_skill_md(source_path, target_name, base), encoding="utf-8"
        )
        created_files.append(skill_md_path)

        hook_path = hooks_dir / "Stop_enforce_gate.py"
        hook_path.write_text(generate_stop_hook(target_name), encoding="utf-8")
        created_files.append(hook_path)

        was_new, msg = register_config(target_name, phases)

        print("=" * 60)
        print("APPLIED")
        print("=" * 60)
        print(f"  Created : {target_path}/SKILL.md")
        print(f"  Created : {target_path}/hooks/Stop_enforce_gate.py")
        print(f"  Config  : {msg}")
        print()
        print("Next steps:")
        print(f"  1. Wire real evidence into phase config in enforce/configs/__init__.py")
        print(f"  2. Write PreToolUse/PostToolUse hooks to emit phase evidence")
        print(f"  3. Run: python tools/migrate_to_ef.py --base {base} --dry-run  # verify")

    except Exception:
        # Rollback partial artifacts
        for f in created_files:
            try:
                f.unlink()
            except OSError:
                pass
        if target_path.exists() and not any(target_path.iterdir()):
            try:
                target_path.rmdir()
            except OSError:
                pass
        raise


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create evidence-first (-ef) skill variants. Full migration or clean abort."
    )
    parser.add_argument(
        "--base", required=True,
        help="Base skill name (e.g. refactor, planning, go)"
    )
    parser.add_argument(
        "--target",
        help="Target skill name (default: {base}-ef)"
    )
    parser.add_argument(
        "--source",
        help="Explicit source skill path (default: skills/<base>/)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print plan without making changes"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Allow overwrite of existing target directory"
    )
    parser.add_argument(
        "--no-validate", action="store_true",
        help="Skip -ef naming validation"
    )

    args = parser.parse_args()
    target_name = args.target or f"{args.base}-ef"
    target_path = resolve_target(args.target, args.base)

    # Layout check
    layout_errors = validate_layout()
    if layout_errors:
        for e in layout_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Naming check
    if not args.no_validate and not target_name.endswith("-ef"):
        print(
            f"ERROR: target '{target_name}' does not end with '-ef'. "
            "Evidence-first skills use the -ef suffix. Pass --no-validate to skip.",
            file=sys.stderr,
        )
        return 1

    # Source resolution
    source_path = resolve_source(args.base, args.source)

    # Source structure check -- ABORT if not migratable
    can_migrate, reason, fm = check_source_structure(source_path)
    if not can_migrate:
        print(f"ERROR: {reason}", file=sys.stderr)
        return 1

    # Target safety check
    if target_path.is_dir() and not args.force:
        print(
            f"ERROR: target {target_path} already exists (use --force to overwrite)",
            file=sys.stderr,
        )
        return 1

    # Derive phases from source structure
    phases = derive_phases_from_source(source_path, target_name)

    # Config status
    if str(ENFORCE_DIR.parent) not in sys.path:
        sys.path.insert(0, str(ENFORCE_DIR.parent))
    from enforce.configs import ENFORCE_CONFIGS
    config_status = (
        "exists" if target_name in ENFORCE_CONFIGS else f"new entry ({_plural(len(phases), 'phase')})"
    )

    blockers: list[str] = []
    if args.dry_run:
        report_dry_run(
            args.base, target_name, source_path, target_path,
            config_status, phases, blockers,
        )
        return 0

    if blockers:
        for b in blockers:
            print(f"ERROR: {b}", file=sys.stderr)
        return 1

    try:
        apply(args.base, target_name, source_path, target_path, args.force, phases)
    except Exception as e:
        print(f"ERROR: migration failed, partial artifacts cleaned up: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())