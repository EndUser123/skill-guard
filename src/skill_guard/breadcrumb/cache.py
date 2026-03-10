#!/usr/bin/env python3
"""
Breadcrumb State Cache
======================

In-memory cache for breadcrumb state with periodic snapshots to disk.

Provides:
- Fast in-memory access (no file I/O on every breadcrumb update)
- Terminal-scoped cache keys for multi-terminal safety
- Periodic snapshots to disk for crash recovery
- Lazy loading from log files on cache miss

Cache Key Format:
    "{skill_name}:terminal:{terminal_id}"

Example:
    >>> cache = BreadcrumbStateCache()
    >>> state = cache.get_state("code")  # Returns None or cached state
    >>> cache.update_state("code", {"completed_steps": ["analyze", "refactor"]})
    >>> cache.snapshot_all()  # Write all cached states to disk
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from skill_guard.breadcrumb.log import AppendOnlyBreadcrumbLog
from skill_guard.utils.terminal_detection import detect_terminal_id

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_DIR = Path("P:/.claude/state")

# Snapshot interval (seconds)
SNAPSHOT_INTERVAL = 30.0

# Maximum number of cached skills
MAX_CACHE_SIZE = 100


# =============================================================================
# CACHE IMPLEMENTATION
# =============================================================================

class BreadcrumbStateCache:
    """In-memory cache for breadcrumb state with terminal-scoped keys.

    Features:
    - Lazy loading: State loaded from log on first access
    - Terminal isolation: Cache keys include terminal_id
    - Periodic snapshots: Auto-save to disk every N seconds
    - Thread-safe: Uses lock for concurrent access
    - LRU eviction: Removes least recently used entries when full

    Example:
        >>> cache = BreadcrumbStateCache()
        >>> state = cache.get_state("code")
        >>> cache.update_state("code", {"completed_steps": ["analyze"]})
        >>> cache.snapshot_all()  # Manual snapshot
    """

    def __init__(self, max_size: int = MAX_CACHE_SIZE) -> None:
        """Initialize breadcrumb state cache.

        Args:
            max_size: Maximum number of skills to cache (default: 100)
        """
        self.max_size = max_size
        self._cache: dict[str, dict[str, Any]] = {}
        self._access_times: dict[str, float] = {}
        self._lock = threading.RLock()
        self._snapshot_interval = SNAPSHOT_INTERVAL
        self._last_snapshot = time.time()

    def _get_cache_key(self, skill_name: str) -> str:
        """Get terminal-scoped cache key for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Cache key string with terminal_id
        """
        terminal_id = detect_terminal_id()
        return f"{skill_name.lower()}:terminal:{terminal_id}"

    def get_state(self, skill_name: str) -> dict[str, Any] | None:
        """Get breadcrumb state from cache (lazy load if miss).

        Args:
            skill_name: Name of the skill

        Returns:
            State dict or None if no state exists
        """
        cache_key = self._get_cache_key(skill_name)

        with self._lock:
            # Cache hit
            if cache_key in self._cache:
                self._access_times[cache_key] = time.time()
                return self._cache[cache_key].copy()

            # Cache miss - lazy load from log
            state = self._load_from_log(skill_name)
            if state:
                self._cache[cache_key] = state
                self._access_times[cache_key] = time.time()
                self._evict_if_needed()
                return state.copy()

            return None

    def update_state(self, skill_name: str, state: dict[str, Any]) -> None:
        """Update breadcrumb state in cache.

        Args:
            skill_name: Name of the skill
            state: State dict to cache

        Note:
            This doesn't write to disk. Call snapshot_all() to persist.
        """
        if not isinstance(state, dict):
            raise ValueError(f"State must be dict, got {type(state)}")

        cache_key = self._get_cache_key(skill_name)

        with self._lock:
            self._cache[cache_key] = state.copy()
            self._access_times[cache_key] = time.time()
            self._evict_if_needed()

    def _load_from_log(self, skill_name: str) -> dict[str, Any] | None:
        """Load state from append-only log (lazy loading).

        Args:
            skill_name: Name of the skill

        Returns:
            State dict reconstructed from log, or None if log doesn't exist
        """
        try:
            log = AppendOnlyBreadcrumbLog(skill_name)
            entries = list(reversed(log.replay()))  # Oldest first for reconstruction

            if not entries:
                return None

            # Reconstruct state from log entries
            # Start with first entry (usually initialization)
            state = entries[0].copy()

            # Apply subsequent entries
            for entry in entries[1:]:
                if entry.get("event") == "step_complete":
                    step = entry.get("step")
                    if step and "completed_steps" in state:
                        if step not in state["completed_steps"]:
                            state["completed_steps"].append(step)

            return state

        except Exception:
            # Return None on any error during log loading
            return None

    def _evict_if_needed(self) -> None:
        """Evict least recently used entry if cache is full."""
        if len(self._cache) <= self.max_size:
            return

        # Find least recently used entry
        lru_key = min(self._access_times, key=self._access_times.get)

        # Evict
        del self._cache[lru_key]
        del self._access_times[lru_key]

    def snapshot_all(self) -> None:
        """Snapshot all cached states to disk.

        Writes each cached state to its breadcrumb file.
        This is called automatically on a timer, but can be called manually.
        """
        with self._lock:
            # Check if snapshot is needed
            now = time.time()
            if now - self._last_snapshot < self._snapshot_interval:
                return

            # Snapshot each cached state
            for cache_key, state in self._cache.items():
                skill_name = cache_key.split(":")[0]  # Extract skill name from key
                self._snapshot_state(skill_name, state)

            self._last_snapshot = now

    def _snapshot_state(self, skill_name: str, state: dict[str, Any]) -> None:
        """Snapshot a single state to disk.

        Args:
            skill_name: Name of the skill
            state: State dict to snapshot
        """
        # Import here to avoid circular import
        from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

        breadcrumb_file = _get_breadcrumb_file(skill_name)

        # Write state to file
        breadcrumb_file.parent.mkdir(parents=True, exist_ok=True)
        breadcrumb_file.write_text(json.dumps(state, indent=2))

    def invalidate(self, skill_name: str) -> None:
        """Remove skill from cache (force reload from log on next access).

        Args:
            skill_name: Name of the skill to invalidate
        """
        cache_key = self._get_cache_key(skill_name)

        with self._lock:
            self._cache.pop(cache_key, None)
            self._access_times.pop(cache_key, None)

    def clear_all(self) -> None:
        """Clear all cached states."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache size, hit rate, and memory usage info
        """
        with self._lock:
            return {
                "cached_skills": len(self._cache),
                "max_size": self.max_size,
                "last_snapshot": self._last_snapshot,
                "snapshot_interval": self._snapshot_interval,
                "keys": list(self._cache.keys()),
            }
