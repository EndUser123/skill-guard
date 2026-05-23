#!/usr/bin/env python3
"""
Unified migration utility for skill-guard.

Combines:
  - EF structural migration (creates -ef skill variants wired to enforce layer)
  - Frontmatter contract migration (audits/patches contract_type, required_artifacts,
    response_requirements fields)

Usage:
    # EF structural migration
    python migrate_skill_ef.py ef --base refactor --dry-run
    python migrate_skill_ef.py ef --base refactor
    python migrate_skill_ef.py ef --base planning --target planning-ef

    # Frontmatter contract migration
    python migrate_skill_ef.py ct --skill gto --plugin cc-skills-analysis
    python migrate_skill_ef.py ct --skill gto --mode patch --write true
    python migrate_skill_ef.py ct --batch --skills-dir P:/packages/.claude-marketplace/plugins/cc-skills-analysis/skills
    python migrate_skill_ef.py ct --all --dry-run

    # Legacy bare --base still works (maps to ef subcommand)
    python migrate_skill_ef.py --base refactor --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure skill_guard package is importable
_SRC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from skill_guard._skill_frontmatter_loader import (
    build_migration_result,
    classify_migration_status,
)

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


# -----------------------------------------------------------------------
# Frontmatter contract migration (absorbed from migrate_skill_ct)
# -----------------------------------------------------------------------

PLUGINS_DIR = Path(os.environ.get("PLUGINS_DIR", r"P:\packages\.claude-marketplace\plugins"))


def _resolve_skill_path(plugin: str | None, skill_name: str) -> tuple[str, Path]:
    """Resolve (plugin_name, skill_file_path) from explicit plugin or auto-search."""
    if plugin:
        plugin_dir = PLUGINS_DIR / plugin
        skill_file = plugin_dir / "skills" / skill_name / "SKILL.md"
        return plugin, skill_file

    candidates = []
    if PLUGINS_DIR.exists():
        for entry in sorted(PLUGINS_DIR.iterdir()):
            if not entry.is_dir():
                continue
            skill_file = entry / "skills" / skill_name / "SKILL.md"
            if skill_file.exists():
                candidates.append((entry.name, skill_file))

    if not candidates:
        raise ValueError(
            f"Skill '{skill_name}' not found in any plugin under {PLUGINS_DIR}. "
            "Use --plugin <name> to specify the plugin explicitly."
        )
    if len(candidates) > 1:
        names = ", ".join(p for p, _ in candidates)
        raise ValueError(
            f"Skill '{skill_name}' found in multiple plugins: {names}. "
            "Use --plugin <name> to disambiguate."
        )

    return candidates[0]


def _load_target_frontmatter(plugin: str | None, skill_name: str) -> dict[str, Any] | None:
    """Load the frontmatter dict for a target skill."""
    try:
        _, skill_file = _resolve_skill_path(plugin, skill_name)
    except ValueError:
        return None
    if not skill_file.exists():
        return None
    try:
        import yaml
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return None
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return None
        return fm_data
    except Exception:
        return None


def _generate_patch(
    frontmatter: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Generate a minimal patch plan from build_migration_result output."""
    changes: list[dict[str, str]] = []
    status = result["status"]
    if status == "MIGRATED":
        return {
            "changes": [],
            "yaml_diff": "No changes needed — skill is already migrated.",
        }

    ct = (frontmatter or {}).get("contract_type", "")
    missing = result.get("missing_fields", [])
    skill_name = result.get("skill", "")

    if "required_artifacts" in missing:
        changes.append({"field": "required_artifacts", "value": "[]"})
    if "response_requirements" in missing:
        changes.append({"field": "response_requirements", "value": "{}"})
    if not ct or ct in {"workflow", "output", "hybrid", "analysis"}:
        if status == "UNMIGRATED":
            changes.append({"field": "contract_type", "value": "workflow-execution"})

    lines = ["# Proposed frontmatter changes:", ""]
    for change in changes:
        lines.append(f"- Add/set {change['field']}: {change['value']}")

    name = (frontmatter or {}).get("name", skill_name) if frontmatter else skill_name
    lines.append("")
    lines.append("# Example YAML:")
    lines.append(f"{name}:")
    for change in changes:
        lines.append(f"  {change['field']}: {change['value']}")

    return {"changes": changes, "yaml_diff": "\n".join(lines)}


def _apply_patch(
    plugin: str | None,
    skill_name: str,
    frontmatter: dict[str, Any],
    changes: list[dict[str, str]],
    skill_file: Path | None = None,
) -> dict[str, Any]:
    """Apply minimal patch to a target skill's SKILL.md atomically."""
    if skill_file is None:
        try:
            _, skill_file = _resolve_skill_path(plugin, skill_name)
        except ValueError as e:
            return {"files_modified": [], "error": str(e)}

    if not skill_file.exists():
        return {"files_modified": [], "error": f"SKILL.md not found at {skill_file}"}

    try:
        import yaml

        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return {"files_modified": [], "error": "SKILL.md missing YAML frontmatter delimiters"}
        fm: dict[str, Any] = yaml.safe_load(parts[1])
        if not isinstance(fm, dict):
            fm = dict(fm) if fm else {}
    except Exception as e:
        return {"files_modified": [], "error": f"Failed to parse YAML: {e}"}

    for change in changes:
        field = change["field"]
        value_raw = change["value"]
        if value_raw == "[]":
            value: Any = []
        elif value_raw == "{}":
            value = {}
        else:
            value = value_raw
        fm[field] = value

    yaml_out = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    new_content = f"---\n{yaml_out}---{''.join(parts[2:])}"

    tmp = skill_file.with_suffix(".md.tmp")
    tmp.write_text(new_content, encoding="utf-8")
    tmp.replace(skill_file)

    return {
        "files_modified": [str(skill_file)],
        "fields_changed": [f"{c['field']}: {c['value']}" for c in changes],
    }


def _verify_patch(plugin: str | None, skill_name: str, skill_file: Path | None = None) -> dict[str, Any]:
    """Re-classify updated frontmatter to verify patch success."""
    try:
        if skill_file is None:
            fm = _load_target_frontmatter(plugin, skill_name)
        else:
            import yaml
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            parts = content.split("---")
            if len(parts) < 3:
                return {"ok": False, "error": "SKILL.md missing YAML frontmatter delimiters"}
            fm = yaml.safe_load(parts[1])
            if not isinstance(fm, dict):
                fm = dict(fm) if fm else {}
    except Exception as e:
        return {"ok": False, "error": f"Failed to re-parse YAML: {e}"}
    if fm is None:
        return {"ok": False, "error": "Could not reload frontmatter after patch"}
    status = classify_migration_status(fm)
    return {"ok": status == "MIGRATED", "status": status}


def _infer_ct(frontmatter: dict[str, Any] | None) -> str:
    """Return the raw contract_type value or 'unset' if absent."""
    if frontmatter is None:
        return "unset"
    ct = frontmatter.get("contract_type")
    if ct is None:
        return "unset"
    if isinstance(ct, str):
        return ct.strip().lower()
    return "unset"


def _load_all_skill_frontmatter(skills_dir: Path) -> dict[str, dict[str, Any] | None]:
    """Discover all skill directories under skills_dir and load their frontmatter."""
    import yaml

    results: dict[str, dict[str, Any] | None] = {}
    if not skills_dir.exists():
        return results
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            continue
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            parts = content.split("---")
            if len(parts) < 2:
                results[entry.name] = None
                continue
            fm_data = yaml.safe_load(parts[1])
            results[entry.name] = fm_data if isinstance(fm_data, dict) else None
        except Exception:
            results[entry.name] = None
    return results


def run_ct_migration(prompt: str) -> dict[str, Any]:
    """Run frontmatter contract migration from a skill invocation prompt."""
    parsed = _parse_ct_prompt(prompt)
    return _do_ct_migration(
        plugin=parsed["plugin"],
        skill_name=parsed["skill_name"],
        mode=parsed["mode"],
        write=parsed["write"],
    )


def _parse_ct_prompt(prompt: str) -> dict[str, Any]:
    """Extract plugin, skill_name, mode, write from a skill invocation prompt."""
    result: dict[str, Any] = {
        "plugin": None,
        "skill_name": "",
        "mode": "audit",
        "write": False,
    }
    prompt = prompt.strip()
    prompt = re.sub(r"^/migrate-skill-(?:ct|ef)\s*", "", prompt, flags=re.IGNORECASE)
    parts = prompt.split()
    if not parts:
        return result

    first = parts[0]
    if ":" in first:
        plugin_part, skill_part = first.split(":", 1)
        result["plugin"] = plugin_part
        result["skill_name"] = skill_part.lstrip("/")
    else:
        result["skill_name"] = first.lstrip("/")

    i = 1
    while i < len(parts):
        lower = parts[i].lower()
        if lower == "--plugin" and i + 1 < len(parts):
            result["plugin"] = parts[i + 1]
            i += 2
        elif lower == "--mode" and i + 1 < len(parts):
            result["mode"] = parts[i + 1].lower()
            i += 2
        elif lower == "--write" and i + 1 < len(parts):
            result["write"] = parts[i + 1].lower() in ("true", "1", "yes")
            i += 2
        elif lower in ("--plugin", "--mode", "--write"):
            if lower == "--plugin":
                result["plugin"] = ""
            elif lower == "--mode":
                result["mode"] = "audit"
            elif lower == "--write":
                result["write"] = True
            i += 1
        else:
            i += 1
    return result


def _do_ct_migration(
    plugin: str | None,
    skill_name: str,
    mode: str = "audit",
    write: bool = False,
) -> dict[str, Any]:
    """Run frontmatter contract migration for a named skill."""
    if not skill_name:
        return {
            "error": (
                "No skill name provided. Usage: /migrate-skill-ef <skill-name> "
                "[--plugin <plugin-name>] [--mode audit|patch] [--write true|false]"
            ),
        }

    if mode not in {"audit", "patch"}:
        return {"error": f"Unknown mode '{mode}'. Use --mode audit or --mode patch.", "skill_name": skill_name}

    try:
        resolved_plugin, skill_file = _resolve_skill_path(plugin, skill_name)
    except ValueError as e:
        return {"error": str(e), "skill_name": skill_name, "plugin": plugin}

    fm = _load_target_frontmatter(plugin, skill_name)
    if fm is None:
        return {
            "error": (
                f"Could not load SKILL.md for skill '{skill_name}'"
                + (f" in plugin '{plugin}'" if plugin else "")
                + f". Checked: {skill_file}"
            ),
            "skill_name": skill_name,
            "plugin": plugin,
        }

    classification = classify_migration_status(fm)
    migration_result = build_migration_result(skill_name, fm)

    if classification == "MIGRATED":
        return {
            "skill_name": skill_name,
            "plugin": resolved_plugin,
            "status": classification,
            "action": "none",
            "reason": migration_result["reason"],
            "missing_fields": [],
            "verification": "Skill already has contract_type and required contract fields. No migration needed.",
        }

    patch_plan = _generate_patch(fm, migration_result)

    if mode == "patch":
        changes = patch_plan["changes"]
        if changes and write:
            apply_result = _apply_patch(plugin, skill_name, fm, changes, skill_file=skill_file)
            if apply_result.get("error"):
                return {
                    "skill_name": skill_name,
                    "plugin": resolved_plugin,
                    "status": classification,
                    "action": "error",
                    "error": apply_result["error"],
                }
            verify_result = _verify_patch(plugin, skill_name, skill_file=skill_file)
            return {
                "skill_name": skill_name,
                "plugin": resolved_plugin,
                "status": classification,
                "action": "applied",
                "files_modified": apply_result.get("files_modified", []),
                "fields_changed": apply_result.get("fields_changed", []),
                "patch": patch_plan["yaml_diff"],
                "verification": verify_result,
            }
        return {
            "skill_name": skill_name,
            "plugin": resolved_plugin,
            "status": classification,
            "action": "plan" if changes else "none",
            "reason": migration_result["reason"],
            "missing_fields": migration_result.get("missing_fields", []),
            "patch": patch_plan["yaml_diff"],
            "verification": (
                "Proposed changes only — use --write true to apply."
                if changes
                else "No changes needed."
            ),
        }

    return {
        "skill_name": skill_name,
        "plugin": resolved_plugin,
        "status": classification,
        "action": "plan",
        "reason": migration_result["reason"],
        "missing_fields": migration_result.get("missing_fields", []),
        "patch": patch_plan["yaml_diff"],
        "verification": "Proposed changes only — no files modified in audit mode.",
    }


def run_batch_audit(skills_dir: Path) -> list[dict[str, Any]]:
    """Audit all skills in skills_dir and return a list of result dicts."""
    frontmatters = _load_all_skill_frontmatter(skills_dir)
    results: list[dict[str, Any]] = []

    for skill_name, fm in frontmatters.items():
        if fm is None:
            results.append({
                "name": skill_name,
                "status": "UNMIGRATED",
                "contract_type": "unset",
                "missing_fields": [],
                "reason": "Could not parse SKILL.md frontmatter.",
            })
            continue

        classification = classify_migration_status(fm)
        migration_result = build_migration_result(skill_name, fm)
        inferred_ct = _infer_ct(fm)

        results.append({
            "name": skill_name,
            "status": classification,
            "contract_type": inferred_ct,
            "missing_fields": migration_result.get("missing_fields", []),
            "reason": migration_result.get("reason", ""),
        })

    return results


def run_bulk_apply(
    skills_dir: Path,
    status_filter: set[str] | None = None,
    write: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Bulk-apply minimal migration patches to skills matching status_filter."""
    if status_filter is None:
        status_filter = {"UNMIGRATED"}

    frontmatters = _load_all_skill_frontmatter(skills_dir)
    results: list[dict[str, Any]] = []

    for skill_name, fm in frontmatters.items():
        if fm is None:
            results.append({
                "name": skill_name,
                "old_status": "UNMIGRATED",
                "new_status": None,
                "action": "skipped",
                "error": "Could not parse SKILL.md frontmatter.",
            })
            continue

        classification = classify_migration_status(fm)
        migration_result = build_migration_result(skill_name, fm)

        if classification not in status_filter:
            results.append({
                "name": skill_name,
                "old_status": classification,
                "new_status": classification,
                "action": "skipped",
                "error": None,
            })
            continue

        patch_plan = _generate_patch(fm, migration_result)
        changes = patch_plan["changes"]

        if not changes:
            results.append({
                "name": skill_name,
                "old_status": classification,
                "new_status": classification,
                "action": "planned",
                "error": "No changes needed.",
            })
            continue

        if dry_run or not write:
            results.append({
                "name": skill_name,
                "old_status": classification,
                "new_status": None,
                "action": "planned",
                "error": None,
                "changes": patch_plan["yaml_diff"],
            })
            continue

        skill_file = skills_dir / skill_name / "SKILL.md"
        apply_result = _apply_patch(None, skill_name, fm, changes, skill_file=skill_file)
        if apply_result.get("error"):
            results.append({
                "name": skill_name,
                "old_status": classification,
                "new_status": None,
                "action": "patched",
                "error": apply_result["error"],
            })
            continue

        verify_result = _verify_patch(None, skill_name, skill_file=skill_file)
        results.append({
            "name": skill_name,
            "old_status": classification,
            "new_status": verify_result.get("status"),
            "action": "patched",
            "error": None,
            "fields_changed": apply_result.get("fields_changed", []),
            "files_modified": apply_result.get("files_modified", []),
        })

    return results


def _print_batch_summary(results: list[dict[str, Any]], skills_dir: Path) -> None:
    """Print a human-readable summary table for batch audit results."""
    total = len(results)
    counts: dict[str, int] = {"MIGRATED": 0, "PARTIALLY_MIGRATED": 0, "UNMIGRATED": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print(f"Batch migration audit for {skills_dir}")
    print(f"{'='*60}")
    print(f"{'STATUS':<20} {'NAME':<30} {'CONTRACT_TYPE':<20} {'MISSING_FIELDS'}")
    print(f"{'-'*20} {'-'*30} {'-'*20} {'-'*20}")

    for r in results:
        missing = ", ".join(r["missing_fields"]) if r["missing_fields"] else "—"
        ct = r["contract_type"]
        name = r["name"]
        status = r["status"]
        print(f"{status:<20} {name:<30} {ct:<20} {missing}")

    print(f"{'-'*20} {'-'*30} {'-'*20} {'-'*20}")
    print(f"Total: {total} skills")
    for status, count in counts.items():
        pct = f" ({count}/{total} = {count*100//max(total,1)}%)" if total else ""
        print(f"  {status}: {count}{pct}")


def _print_bulk_summary(results: list[dict[str, Any]], skills_dir: Path) -> None:
    """Print a human-readable summary for bulk apply results."""
    total = len(results)
    actions: dict[str, int] = {"patched": 0, "planned": 0, "skipped": 0}
    old_counts: dict[str, int] = {"MIGRATED": 0, "PARTIALLY_MIGRATED": 0, "UNMIGRATED": 0}
    new_counts: dict[str, int] = {"MIGRATED": 0, "PARTIALLY_MIGRATED": 0, "UNMIGRATED": 0}

    for r in results:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
        old_counts[r["old_status"]] = old_counts.get(r["old_status"], 0) + 1
        ns = r.get("new_status") or r.get("old_status", "UNKNOWN")
        new_counts[ns] = new_counts.get(ns, 0) + 1

    print(f"Bulk apply results for {skills_dir}")
    print(f"{'='*60}")
    print(f"{'ACTION':<12} {'NAME':<30} {'OLD_STATUS':<20} {'NEW_STATUS':<20} {'ERROR'}")
    print(f"{'-'*12} {'-'*30} {'-'*20} {'-'*20} {'-'*20}")

    for r in results:
        err = r.get("error", "") or "—"
        old = r["old_status"]
        new = r.get("new_status") or "—"
        print(f"{r['action']:<12} {r['name']:<30} {old:<20} {new:<20} {err}")

    print(f"{'-'*12} {'-'*30} {'-'*20} {'-'*20} {'-'*20}")
    print(f"Total scanned: {total}")
    print(f"  patched: {actions.get('patched', 0)}")
    print(f"  planned: {actions.get('planned', 0)}")
    print(f"  skipped: {actions.get('skipped', 0)}")
    print("Status before → after:")
    for status in ("MIGRATED", "PARTIALLY_MIGRATED", "UNMIGRATED"):
        before = old_counts.get(status, 0)
        after = new_counts.get(status, 0)
        print(f"  {status}: {before} → {after}")


# -----------------------------------------------------------------------
# Unified CLI (EF structural migration + frontmatter contract migration)
# -----------------------------------------------------------------------

def _ct_main(args: argparse.Namespace) -> int:
    """Handle frontmatter contract migration subcommands."""
    effective_skills_dir: Path | None = None
    if args.skills_dir:
        effective_skills_dir = Path(args.skills_dir)
    elif args.batch or args.all:
        effective_skills_dir = PLUGINS_DIR

    # Single-skill mode
    if args.skill and not args.batch and not args.all:
        plugin = args.plugin
        result = _do_ct_migration(
            plugin=plugin,
            skill_name=args.skill,
            mode=args.mode,
            write=args.write == "true",
        )
        print(json.dumps(result, indent=2))
        return 0

    # Batch audit mode
    if args.batch:
        if not effective_skills_dir:
            print("ERROR: --batch requires --skills-dir or PLUGINS_DIR to be set", file=sys.stderr)
            return 1
        results = run_batch_audit(effective_skills_dir)
        _print_batch_summary(results, effective_skills_dir)
        return 0

    # Bulk apply mode
    if args.all:
        if not effective_skills_dir:
            print("ERROR: --all requires --skills-dir or PLUGINS_DIR to be set", file=sys.stderr)
            return 1
        status_filter = set(args.status_filter) if args.status_filter else {"UNMIGRATED"}
        write = args.write == "true" and not args.dry_run
        results = run_bulk_apply(
            skills_dir=effective_skills_dir,
            status_filter=status_filter,
            write=write,
            dry_run=args.dry_run,
        )
        _print_bulk_summary(results, effective_skills_dir)
        return 0

    print("ERROR: Specify --skill <name> for single-skill mode, or --batch / --all for batch mode.", file=sys.stderr)
    return 1


def _ef_main(args: argparse.Namespace) -> int:
    """Handle EF structural migration."""
    target_name = args.target or f"{args.base}-ef"
    target_path = resolve_target(args.target, args.base)

    layout_errors = validate_layout()
    if layout_errors:
        for e in layout_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not args.no_validate and not target_name.endswith("-ef"):
        print(
            f"ERROR: target '{target_name}' does not end with '-ef'. "
            "Evidence-first skills use the -ef suffix. Pass --no-validate to skip.",
            file=sys.stderr,
        )
        return 1

    source_path = resolve_source(args.base, args.source)
    can_migrate, reason, fm = check_source_structure(source_path)
    if not can_migrate:
        print(f"ERROR: {reason}", file=sys.stderr)
        return 1

    if target_path.is_dir() and not args.force:
        print(
            f"ERROR: target {target_path} already exists (use --force to overwrite)",
            file=sys.stderr,
        )
        return 1

    phases = derive_phases_from_source(source_path, target_name)

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified migration tool: EF structural migration + frontmatter contract migration.",
    )

    sub = parser.add_subparsers(dest="command")

    # EF structural migration (original --base mode)
    ef_p = sub.add_parser("ef", help="Create evidence-first (-ef) skill variants")
    ef_p.add_argument("--base", required=True, help="Base skill name (e.g. refactor, planning, go)")
    ef_p.add_argument("--target", help="Target skill name (default: {base}-ef)")
    ef_p.add_argument("--source", help="Explicit source skill path")
    ef_p.add_argument("--dry-run", action="store_true", help="Print plan without making changes")
    ef_p.add_argument("--force", action="store_true", help="Allow overwrite of existing target directory")
    ef_p.add_argument("--no-validate", action="store_true", help="Skip -ef naming validation")

    # Frontmatter contract migration (absorbed from _ct)
    ct_p = sub.add_parser("ct", help="Audit/patch frontmatter contract fields")
    ct_p.add_argument("--skill", help="Name of the skill to migrate (single-skill mode)")
    ct_p.add_argument("--plugin", help="Plugin name (e.g. cc-skills-analysis)")
    ct_p.add_argument("--mode", choices=["audit", "patch"], default="audit", help="Mode: audit (default) or patch")
    ct_p.add_argument("--write", choices=["true", "false"], default="false", help="Apply changes (true) or just propose (false)")
    ct_p.add_argument("--batch", action="store_true", help="Audit all skills in --skills-dir")
    ct_p.add_argument("--skills-dir", help="Override the skills directory for --batch")
    ct_p.add_argument("--all", action="store_true", help="Apply migration patches to all skills matching --status-filter")
    ct_p.add_argument("--status-filter", nargs="+", default=None, help="Which statuses to act on in --all mode")
    ct_p.add_argument("--dry-run", action="store_true", help="In --all mode, plan changes without applying")

    # Legacy: bare --base still works (maps to ef subcommand)
    parser.add_argument("--base", help=argparse.SUPPRESS)
    parser.add_argument("--target", help=argparse.SUPPRESS)
    parser.add_argument("--source", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-validate", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Legacy bare --base support (no subcommand given)
    if args.command is None and args.base:
        args.command = "ef"

    if args.command == "ef":
        return _ef_main(args)
    elif args.command == "ct":
        return _ct_main(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())