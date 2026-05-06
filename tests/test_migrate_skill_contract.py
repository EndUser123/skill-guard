"""Tests for migrate-skill-contract skill."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure skill_guard src and skills packages are importable
skill_guard_root = str(Path(__file__).parent.parent.resolve())
hooks_path = str(Path(r"P:\.claude\hooks").resolve())
for _p in (hooks_path, skill_guard_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from skills.migrate_skill_ct import (
    _apply_patch,
    _do_migration,
    _generate_patch,
    _infer_contract_type,
    _load_all_skill_frontmatter,
    _load_target_frontmatter,
    _parse_prompt,
    _verify_patch,
    run_batch_audit,
    run_bulk_apply,
    run_migration,
)


class TestParseInvocation:
    def test_basic_skill_name(self):
        result = _parse_prompt("/migrate-skill-ct trace")
        assert result["skill_name"] == "trace"
        assert result["mode"] == "audit"
        assert result["write"] is False

    def test_mode_audit(self):
        result = _parse_prompt("/migrate-skill-ct decision-tree --mode audit")
        assert result["skill_name"] == "decision-tree"
        assert result["mode"] == "audit"

    def test_mode_patch(self):
        result = _parse_prompt("/migrate-skill-ct gto --mode patch")
        assert result["skill_name"] == "gto"
        assert result["mode"] == "patch"

    def test_write_true(self):
        result = _parse_prompt("/migrate-skill-ct gto --mode patch --write true")
        assert result["skill_name"] == "gto"
        assert result["mode"] == "patch"
        assert result["write"] is True

    def test_write_false(self):
        result = _parse_prompt("/migrate-skill-ct gto --write false")
        assert result["skill_name"] == "gto"
        assert result["write"] is False

    def test_no_skill_name(self):
        result = _parse_prompt("/migrate-skill-ct")
        assert result["skill_name"] == ""


class TestRunMigrationResultShape:
    """Basic result shape tests without requiring real skill files."""

    def test_missing_skill_returns_error(self):
        result = run_migration("/migrate-skill-ct nonexistent-skill-xyz")
        assert "error" in result
        assert result["skill_name"] == "nonexistent-skill-xyz"

    def test_no_skill_name_returns_error(self):
        result = run_migration("/migrate-skill-ct")
        assert "error" in result
        assert "No skill name provided" in result["error"]

    def test_unknown_mode_returns_error(self):
        result = run_migration("/migrate-skill-ct trace --mode invalid")
        assert "error" in result
        assert "Unknown mode" in result["error"]


class TestGeneratePatch:
    """Patch generation for unmigrated and partially migrated cases."""

    def test_unmigrated_generates_contract_type_and_required_artifacts(self):
        fm = {"enforcement": "advisory", "description": "A legacy skill"}
        result = {
            "skill": "test-skill",
            "status": "UNMIGRATED",
            "reason": "legacy",
            "missing_fields": ["required_artifacts", "response_requirements"],
        }
        patch = _generate_patch(fm, result)
        assert patch["changes"]
        fields = {c["field"] for c in patch["changes"]}
        assert "contract_type" in fields
        assert "required_artifacts" in fields

    def test_partially_migrated_generates_missing_field(self):
        fm = {
            "contract_type": "workflow-execution",
            "allowed_tools_now": ["Bash"],
        }
        result = {
            "skill": "test-skill",
            "status": "PARTIALLY_MIGRATED",
            "reason": "missing required_artifacts",
            "missing_fields": ["required_artifacts"],
        }
        patch = _generate_patch(fm, result)
        assert patch["changes"]
        fields = {c["field"] for c in patch["changes"]}
        assert "required_artifacts" in fields

    def test_migrated_returns_no_changes(self):
        fm = {
            "contract_type": "workflow-execution",
            "required_artifacts": ["out.json"],
        }
        result = {
            "skill": "test-skill",
            "status": "MIGRATED",
            "action": "none",
            "reason": "already migrated",
            "missing_fields": [],
        }
        patch = _generate_patch(fm, result)
        assert patch["changes"] == []
        assert "No changes needed" in patch["yaml_diff"]


class TestApplyPatchErrors:
    """Patch application edge cases."""

    def test_apply_patch_nonexistent_skill_returns_error(self):
        result = _apply_patch("nonexistent-skill-xyz", {}, [])
        assert "error" in result
        assert "not found" in result["error"].lower() or "nonexistent" in result["error"].lower()


class TestVerifyPatch:
    """Verification of patch results."""

    def test_verify_nonexistent_skill_returns_not_ok(self):
        result = _verify_patch("nonexistent-skill-xyz")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Batch audit tests
# ---------------------------------------------------------------------------

class TestBatchAudit:
    """Tests for run_batch_audit and --batch CLI mode."""

    def test_batch_audit_returns_results_for_all_skills(self, tmp_path):
        """Verify batch audit discovers and classifies all mock skills."""
        # Create three mock skills: migrated, unmigrated, partially migrated
        _write_skill(tmp_path, "skill-migrated", {
            "name": "skill-migrated",
            "contract_type": "workflow-execution",
            "required_artifacts": [],
            "response_requirements": {},
        })
        _write_skill(tmp_path, "skill-unmigrated", {
            "name": "skill-unmigrated",
            "description": "A legacy skill",
            "enforcement": "advisory",
        })
        _write_skill(tmp_path, "skill-partial", {
            "name": "skill-partial",
            "contract_type": "workflow-execution",
            # missing required_artifacts and response_requirements
        })

        results = run_batch_audit(tmp_path)

        assert len(results) == 3
        by_name = {r["name"]: r for r in results}

        assert by_name["skill-migrated"]["status"] == "MIGRATED"
        assert by_name["skill-unmigrated"]["status"] == "UNMIGRATED"
        assert by_name["skill-partial"]["status"] == "PARTIALLY_MIGRATED"

    def test_batch_audit_returns_unmigrated_for_malformed_skills(self, tmp_path):
        """Malformed frontmatter should be classified UNMIGRATED with an error."""
        # Skill with valid YAML but no frontmatter block
        malformed_file = tmp_path / "skill-bad" / "SKILL.md"
        malformed_file.parent.mkdir()
        malformed_file.write_text("This is not YAML frontmatter.", encoding="utf-8")

        results = run_batch_audit(tmp_path)
        assert len(results) == 1
        assert results[0]["name"] == "skill-bad"
        assert results[0]["status"] == "UNMIGRATED"
        assert "Could not parse" in results[0]["reason"]

    def test_batch_audit_infers_contract_type(self, tmp_path):
        """Verify contract_type is correctly inferred and reported."""
        _write_skill(tmp_path, "skill-legacy", {
            "name": "skill-legacy",
            "contract_type": "workflow",  # legacy type
        })
        _write_skill(tmp_path, "skill-era", {
            "name": "skill-era",
            "contract_type": "workflow-execution",  # contract-era type
        })
        _write_skill(tmp_path, "skill-no-ct", {
            "name": "skill-no-ct",
            "description": "No contract_type set",
        })

        results = run_batch_audit(tmp_path)
        by_name = {r["name"]: r for r in results}

        assert by_name["skill-legacy"]["contract_type"] == "workflow"
        assert by_name["skill-era"]["contract_type"] == "workflow-execution"
        assert by_name["skill-no-ct"]["contract_type"] == "unset"

    def test_batch_audit_shows_missing_fields(self, tmp_path):
        """UNMIGRATED skills should have missing_fields populated."""
        _write_skill(tmp_path, "skill-unmigrated", {
            "name": "skill-unmigrated",
            "enforcement": "advisory",
        })

        results = run_batch_audit(tmp_path)
        assert len(results) == 1
        assert results[0]["status"] == "UNMIGRATED"
        assert "required_artifacts" in results[0]["missing_fields"]
        assert "response_requirements" in results[0]["missing_fields"]

    def test_batch_audit_does_not_write_files(self, tmp_path):
        """Batch audit must be purely read-only — no file modifications."""
        _write_skill(tmp_path, "skill-a", {
            "name": "skill-a",
            "contract_type": "workflow-execution",
            "required_artifacts": [],
        })
        _write_skill(tmp_path, "skill-b", {
            "name": "skill-b",
            "enforcement": "advisory",
        })

        # Record existing file hashes
        def md5(path):
            import hashlib
            return hashlib.md5(path.read_bytes()).hexdigest()

        before = {n: md5(tmp_path / n / "SKILL.md") for n in ("skill-a", "skill-b")}

        results = run_batch_audit(tmp_path)

        after = {n: md5(tmp_path / n / "SKILL.md") for n in ("skill-a", "skill-b")}
        assert before == after, "Batch audit modified files — it must be read-only"

    def test_batch_audit_skips_dirs_without_skill_md(self, tmp_path):
        """Directories without SKILL.md should not appear in results."""
        tmp_path.joinpath("no-skill-dir").mkdir()
        tmp_path.joinpath("not-a-dir.txt").write_text("not a skill", encoding="utf-8")
        _write_skill(tmp_path, "skill-real", {
            "name": "skill-real",
        })

        results = run_batch_audit(tmp_path)
        names = {r["name"] for r in results}
        assert names == {"skill-real"}


class TestBulkApply:
    """Tests for run_bulk_apply and --all CLI mode."""

    def test_bulk_apply_patches_only_filtered_status(self, tmp_path):
        """Only skills matching status_filter should be acted on."""
        _write_skill(tmp_path, "skill-a", {
            "name": "skill-a",
            "enforcement": "advisory",  # UNMIGRATED
        })
        _write_skill(tmp_path, "skill-b", {
            "name": "skill-b",
            "contract_type": "workflow-execution",
            "required_artifacts": [],
        })  # MIGRATED

        # Default filter: UNMIGRATED only
        results = run_bulk_apply(tmp_path, status_filter={"UNMIGRATED"}, write=False, dry_run=False)

        by_name = {r["name"]: r for r in results}
        assert by_name["skill-a"]["action"] == "planned"
        assert by_name["skill-b"]["action"] == "skipped"

    def test_bulk_apply_dry_run_no_files_modified(self, tmp_path):
        """Dry run must never write files."""
        _write_skill(tmp_path, "skill-x", {
            "name": "skill-x",
            "enforcement": "advisory",
        })

        def md5(path):
            import hashlib
            return hashlib.md5(path.read_bytes()).hexdigest()

        before = md5(tmp_path / "skill-x" / "SKILL.md")
        results = run_bulk_apply(tmp_path, status_filter={"UNMIGRATED"}, write=True, dry_run=True)
        after = md5(tmp_path / "skill-x" / "SKILL.md")

        assert results[0]["action"] == "planned"
        assert before == after, "dry_run=True modified files"

    def test_bulk_apply_writes_when_enabled(self, tmp_path):
        """write=True and dry_run=False should apply patches."""
        _write_skill(tmp_path, "skill-y", {
            "name": "skill-y",
            "enforcement": "advisory",
        })

        results = run_bulk_apply(tmp_path, status_filter={"UNMIGRATED"}, write=True, dry_run=False)
        assert results[0]["action"] == "patched"
        assert results[0]["files_modified"]

        # Verify new classification
        fm_results = run_batch_audit(tmp_path)
        skill_y = next(r for r in fm_results if r["name"] == "skill-y")
        assert skill_y["status"] == "MIGRATED"

    def test_bulk_apply_default_filter_ignores_migrated(self, tmp_path):
        """Default status_filter should not touch MIGRATED skills."""
        _write_skill(tmp_path, "skill-done", {
            "name": "skill-done",
            "contract_type": "workflow-execution",
            "required_artifacts": [],
        })

        # Call without explicit status_filter (uses default UNMIGRATED)
        results = run_bulk_apply(tmp_path, write=True, dry_run=False)
        assert results[0]["action"] == "skipped"

    def test_bulk_apply_reports_before_after_status(self, tmp_path):
        """Patched skills should show old_status and new_status in results."""
        _write_skill(tmp_path, "skill-z", {
            "name": "skill-z",
            "enforcement": "advisory",
        })

        results = run_bulk_apply(tmp_path, status_filter={"UNMIGRATED"}, write=True, dry_run=False)
        assert results[0]["old_status"] == "UNMIGRATED"
        assert results[0]["new_status"] == "MIGRATED"

    def test_bulk_apply_no_changes_skills_already_complete(self, tmp_path):
        """Skills with no missing_fields should be 'planned' not 'patched'."""
        _write_skill(tmp_path, "skill-empty", {
            "name": "skill-empty",
            "contract_type": "workflow-execution",
            "required_artifacts": [],
        })  # MIGRATED — no missing fields

        results = run_bulk_apply(tmp_path, status_filter={"MIGRATED"}, write=True, dry_run=False)
        assert results[0]["action"] == "planned"
        assert "No changes needed" in results[0]["error"]

    def test_bulk_apply_malformed_frontmatter_skipped(self, tmp_path):
        """Skills that can't be parsed should be skipped with an error."""
        bad_file = tmp_path / "skill-corrupt" / "SKILL.md"
        bad_file.parent.mkdir()
        bad_file.write_text("NOT VALID YAML <<<<", encoding="utf-8")

        results = run_bulk_apply(tmp_path, status_filter={"UNMIGRATED"}, write=True, dry_run=False)
        assert results[0]["name"] == "skill-corrupt"
        assert results[0]["action"] == "skipped"
        assert "Could not parse" in results[0]["error"]


def _write_skill(base: Path, name: str, frontmatter: dict) -> None:
    """Write a mock SKILL.md with given frontmatter into a temp directory."""
    import yaml

    skill_dir = base / name
    skill_dir.mkdir(exist_ok=True)
    fm_lines = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False).strip().splitlines()
    content = "---\n" + "\n".join(fm_lines) + "\n---\n\n# Mock skill prose\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
