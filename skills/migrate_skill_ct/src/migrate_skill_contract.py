r"""Migration orchestrator for migrate-skill-ct skill.

Wraps existing skill-guard helpers to provide audit and patch modes
for migrating target skills to the execution-contract frontmatter model.

Usage:
    python migrate_skill_contract.py [--skill <name>] [--mode audit|patch] [--write]

Or import run_migration() directly:
    from skills.migrate_skill_ct import run_migration
    result = run_migration("/migrate-skill-ct trace")
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_script_path = Path(__file__)
for _hooks_root in (
    Path(r"$CLAUDE_ROOT/hooks"),
    _script_path.parent.parent.parent,
    _script_path.resolve().parent.parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)

from skill_guard._skill_frontmatter_loader import (
    build_migration_result,
    classify_migration_status,
)

# Primary skill directory — also used by _load_skill_frontmatter in skill_guard.
# Override via SKILL_DIR env var or the --skills-dir argument.
SKILL_DIR = Path(os.environ.get("SKILL_DIR", r"P:\\\\\\packages/.claude-marketplace/plugins/cc-skills-thinking/skills"))


def _load_target_frontmatter(skill_name: str, skills_dir: Path | None = None) -> dict[str, Any] | None:
    """Load the frontmatter dict for a target skill.r"""
    skill_file = (skills_dir or SKILL_DIR) / skill_name / "SKILL.md"
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
    """Generate a minimal patch plan from build_migration_result output.r"""
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

    # Recommend -ct suffix for contract-era skills
    ct_value = None
    for c in changes:
        if c["field"] == "contract_type":
            ct_value = c["value"]
    existing_ct = (frontmatter or {}).get("contract_type", "")
    is_contract_ct = existing_ct in {
        "workflow-execution", "structured-output", "hybrid"
    } or ct_value in {"workflow-execution", "structured-output", "hybrid"}
    should_have_ct = is_contract_ct and not skill_name.endswith("-ct")
    if should_have_ct:
        suggested = f"{skill_name}-ct"
        lines.append("")
        lines.append(f"# Naming recommendation: rename skill directory and 'name:' field to '{suggested}'")
        lines.append(fr"# See: P:\\\\\\.claude/docs/claude-skill-v1.0.md § Naming conventions")
        lines.append("# then run: /migrate-skill-ct <new-name> --mode patch --write true")

    lines.append("")
    lines.append("# Example YAML:")
    name = (frontmatter or {}).get("name", skill_name) if frontmatter else skill_name
    lines.append(f"{name}:")
    for change in changes:
        lines.append(f"  {change['field']}: {change['value']}")

    return {"changes": changes, "yaml_diff": "\n".join(lines)}


def _apply_patch(
    skill_name: str,
    frontmatter: dict[str, Any],
    changes: list[dict[str, str]],
    skills_dir: Path | None = None,
) -> dict[str, Any]:
    """Apply minimal patch to a target skill's SKILL.md atomically."""
    skill_file = (skills_dir or SKILL_DIR) / skill_name / "SKILL.md"
    if not skill_file.exists():
        return {"files_modified": [], "error": f"SKILL.md not found at {skill_file}"}

    try:
        import yaml

        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return {"files_modified": [], "error": "SKILL.md missing YAML frontmatter delimiters"}
        yaml_block = parts[1]
        fm: dict[str, Any] = yaml.safe_load(yaml_block)
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
        elif field == "contract_type":
            value = value_raw
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
        "fields_changed": [f"{c['field']}: {c['valuer']}" for c in changes],
    }


def _verify_patch(skill_name: str, skills_dir: Path | None = None) -> dict[str, Any]:
    """Re-classify updated frontmatter to verify patch success."""
    fm = _load_target_frontmatter(skill_name, skills_dir=skills_dir)
    if fm is None:
        return {"ok": False, "error": "Could not reload frontmatter after patch"}
    status = classify_migration_status(fm)
    return {"ok": status == "MIGRATED", "status": status}


def run_migration(prompt: str) -> dict[str, Any]:
    """Main entrypoint — parse prompt and run migration.

    Args:
        prompt: The full skill invocation prompt, e.g. "/migrate-skill-ct trace --mode patch --write"

    Returns:
        Dict with skill_name, status, action, reason, missing_fields,
        patch (proposed diff), files_modified, fields_changed, verification.
    """
    parsed = _parse_prompt(prompt)
    return _do_migration(
        skill_name=parsed["skill_name"],
        mode=parsed["mode"],
        write=parsed["write"],
    )


def _parse_prompt(prompt: str) -> dict[str, Any]:
    """Extract skill_name, mode, write from a skill invocation prompt."""
    result: dict[str, Any] = {
        "skill_name": "",
        "mode": "audit",
        "write": False,
    }
    prompt = prompt.strip()
    prompt = re.sub(r"^/migrate-skill-ct\s*", "", prompt, flags=re.IGNORECASE)
    parts = prompt.split()
    if not parts:
        return result
    result["skill_name"] = parts[0].lstrip("/")

    i = 1
    while i < len(parts):
        lower = parts[i].lower()
        if lower == "--mode" and i + 1 < len(parts):
            result["mode"] = parts[i + 1].lower()
            i += 2
        elif lower == "--write" and i + 1 < len(parts):
            result["write"] = parts[i + 1].lower() in ("true", "1", "yes")
            i += 2
        elif lower in ("--mode", "--write"):
            if i + 1 < len(parts):
                if lower == "--mode":
                    result["mode"] = parts[i + 1].lower()
                else:
                    result["write"] = parts[i + 1].lower() in ("true", "1", "yes")
            i += 2
        else:
            i += 1
    return result


def _do_migration(
    skill_name: str,
    mode: str = "audit",
    write: bool = False,
) -> dict[str, Any]:
    """Run migration for a named skill."""
    if not skill_name:
        return {
            "error": (
                "No skill name provided. Usage: /migrate-skill-ct <skill-name> "
                "[--mode audit|patch] [--write true|false]"
            ),
        }

    if mode not in {"audit", "patch"}:
        return {"error": f"Unknown mode '{mode}'. Use --mode audit or --mode patch.", "skill_name": skill_name}

    frontmatter = _load_target_frontmatter(skill_name)
    if frontmatter is None:
        return {
            "error": (
                f"Could not load SKILL.md for skill '{skill_name}'. "
                f"Checked: {SKILL_DIR / skill_name / 'SKILL.md'}"
            ),
            "skill_name": skill_name,
        }

    classification = classify_migration_status(frontmatter)
    migration_result = build_migration_result(skill_name, frontmatter)

    if classification == "MIGRATED":
        return {
            "skill_name": skill_name,
            "status": classification,
            "action": "none",
            "reason": migration_result["reason"],
            "missing_fields": [],
            "verification": "Skill already has contract_type and required contract fields. No migration needed.",
        }

    patch_plan = _generate_patch(frontmatter, migration_result)

    if mode == "patch":
        changes = patch_plan["changes"]
        if changes and write:
            apply_result = _apply_patch(skill_name, frontmatter, changes)
            if apply_result.get("error"):
                return {
                    "skill_name": skill_name,
                    "status": classification,
                    "action": "error",
                    "error": apply_result["error"],
                }
            verify_result = _verify_patch(skill_name, skills_dir=None)
            return {
                "skill_name": skill_name,
                "status": classification,
                "action": "applied",
                "files_modified": apply_result.get("files_modified", []),
                "fields_changed": apply_result.get("fields_changed", []),
                "patch": patch_plan["yaml_diff"],
                "verification": verify_result,
            }
        return {
            "skill_name": skill_name,
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
        "status": classification,
        "action": "plan",
        "reason": migration_result["reason"],
        "missing_fields": migration_result.get("missing_fields", []),
        "patch": patch_plan["yaml_diff"],
        "verification": "Proposed changes only — no files modified in audit mode.",
    }


def _infer_contract_type(frontmatter: dict[str, Any] | None) -> str:
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
    """Discover all skill directories under skills_dir and load their frontmatter.

    Returns a dict mapping skill_name -> frontmatter dict (or None if not found/parseable).
    Only includes directories that have a SKILL.md file.
    """
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


def run_batch_audit(skills_dir: Path) -> list[dict[str, Any]]:
    """Audit all skills in skills_dir and return a list of result dicts.

    Each result dict contains: name, status, contract_type, missing_fields,
    reason. Malformed or unreadable skills are included with status UNMIGRATED
    and a descriptive error message.
    """
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
        inferred_ct = _infer_contract_type(fm)

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
    """Bulk-apply minimal migration patches to skills matching status_filter.

    Args:
        skills_dir: Root skills directory to scan.
        status_filter: Set of statuses to act on (e.g. {"UNMIGRATED"}). Defaults to {"UNMIGRATED"}.
        write: If True, apply patches. If False (or dry_run is True), plan only.
        dry_run: If True, never write even if write is True.

    Returns a list of result dicts per skill, each with:
        name, old_status, new_status, action (skipped|planned|patched), error.
    """
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

        apply_result = _apply_patch(skill_name, fm, changes, skills_dir=skills_dir)
        if apply_result.get("error"):
            results.append({
                "name": skill_name,
                "old_status": classification,
                "new_status": None,
                "action": "patched",
                "error": apply_result["error"],
            })
            continue

        verify_result = _verify_patch(skill_name, skills_dir=skills_dir)
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit and optionally patch a skill's execution-contract frontmatter.",
    )
    parser.add_argument("--skill", help="Name of the skill to migrate (required for single-skill mode)")
    parser.add_argument(
        "--mode",
        choices=["audit", "patch"],
        default="audit",
        help="Mode: audit (default) or patch",
    )
    parser.add_argument(
        "--write",
        choices=["true", "false"],
        default="false",
        help="Apply changes (true) or just propose (false, default)",
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help=r"Override the skills directory (default: P:\\\\\\packages/.claude-marketplace/plugins/cc-skills-thinking/skills)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Audit all skills in --skills-dir. Read-only; prints a summary table.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply migration patches to all skills matching --status-filter. Implies --mode patch.",
    )
    parser.add_argument(
        "--status-filter",
        nargs="+",
        default=None,
        help="Which statuses to act on in --all mode. Defaults to UNMIGRATED. "
             "Allowed: UNMIGRATED PARTIALLY_MIGRATED MIGRATED",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="In --all mode, plan changes without applying them.",
    )
    args = parser.parse_args()

    if args.skills_dir:
        global SKILL_DIR
        SKILL_DIR = Path(args.skills_dir)

    effective_skills_dir = SKILL_DIR

    # Batch audit mode: read-only scan of all skills
    if args.batch:
        results = run_batch_audit(effective_skills_dir)
        _print_batch_summary(results, effective_skills_dir)
        return

    # Bulk apply mode
    if args.all:
        status_filter = set(args.status_filter) if args.status_filter else {"UNMIGRATED"}
        write = args.write == "true" and not args.dry_run
        results = run_bulk_apply(
            skills_dir=effective_skills_dir,
            status_filter=status_filter,
            write=write,
            dry_run=args.dry_run,
        )
        _print_bulk_summary(results, effective_skills_dir)
        return

    # Single-skill mode
    if not args.skill:
        parser.error("--skill is required when --batch and --all are not specified")
        return

    result = _do_migration(
        skill_name=args.skill,
        mode=args.mode,
        write=args.write == "true",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
