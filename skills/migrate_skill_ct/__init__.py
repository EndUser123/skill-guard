"""migrate-skill-ct: audit and patch target skills to execution-contract model."""

from __future__ import annotations

from skills.migrate_skill_ct.src.migrate_skill_contract import (
    _apply_patch,
    _do_migration,
    _generate_patch,
    _infer_contract_type,
    _load_all_skill_frontmatter,
    _load_target_frontmatter,
    _parse_prompt,
    _resolve_skill_path,
    _verify_patch,
    main,
    run_batch_audit,
    run_bulk_apply,
    run_migration,
)

__all__ = [
    "run_migration",
    "_do_migration",
    "_parse_prompt",
    "_load_target_frontmatter",
    "_resolve_skill_path",
    "_generate_patch",
    "_apply_patch",
    "_verify_patch",
    "_load_all_skill_frontmatter",
    "_infer_contract_type",
    "run_batch_audit",
    "run_bulk_apply",
    "main",
]


# Also expose at the skill's own namespace so callers can use either:
#   from skills.migrate_skill_ct import run_migration
#   from skills.migrate_skill_ct.src.migrate_skill_contract import run_migration
