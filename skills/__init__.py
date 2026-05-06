"""skill-guard skills package.

Skill modules in this directory can be imported directly:

    from skills.migrate_skill_ct import run_migration

Or use the submodule path:

    from skills.migrate_skill_ct.src.migrate_skill_contract import run_migration
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the skill packages are discoverable when skills/ is on sys.path
# This allows `from skills.migrate_skill_ct import ...` to resolve.
_pass = None  # placeholder — no top-level imports that cause circular deps
