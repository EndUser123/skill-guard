from __future__ import annotations

from pathlib import Path

from skill_guard.breadcrumb.cache import BreadcrumbStateCache

# Import hybrid logging components

# Import terminal detection from skill_guard utilities

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")
# Maximum age for breadcrumb trails (2 hours)
MAX_TRAIL_AGE_SECONDS = 7200

# Global cache instance (terminal-scoped keys for multi-terminal safety)
_cache = BreadcrumbStateCache()
