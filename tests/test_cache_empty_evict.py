"""
Characterization test for PERF-006: ValueError from min() on empty _access_times.

These tests CAPTURE CURRENT BEHAVIOR before the bug fix.
The bug: _evict_if_needed() calls min(_access_times) without checking if _access_times is empty.

Location: skill_guard/breadcrumb/cache.py:181
Finding: PERF-006

Run with: pytest P:/packages/skill-guard/tests/test_cache_empty_evict.py -v
"""

import pytest

from skill_guard.breadcrumb.cache import BreadcrumbStateCache


class TestEvictOnEmptyAccessTimes:
    """Tests for _evict_if_needed() behavior when _access_times is empty."""

    def test_evict_if_needed_raises_valueerror_on_empty_access_times(self):
        """
        Characterization: Calling _evict_if_needed() when _access_times is empty
        raises ValueError from min().

        Given: A BreadcrumbStateCache with empty _access_times but non-empty _cache
        When:  _evict_if_needed() is called
        Then:  ValueError is raised (min() on empty sequence)

        This documents the CURRENT BROKEN BEHAVIOR - the fix should prevent this.
        """
        cache = BreadcrumbStateCache()
        # Force inconsistent state: _cache has entry but _access_times is empty
        cache._cache["test:terminal:123"] = {"completed_steps": ["test"]}
        # _access_times is intentionally empty

        with pytest.raises(ValueError):
            cache._evict_if_needed()

    def test_evict_if_needed_raises_valueerror_when_cache_exceeds_max_size(self):
        """
        Characterization: When _cache has more entries than max_size but
        _access_times is empty, _evict_if_needed() raises ValueError.

        Given: Cache where len(_cache) > max_size but _access_times is empty
        When:  _evict_if_needed() is called
        Then:  ValueError is raised from min(empty_dict)
        """
        cache = BreadcrumbStateCache(max_size=1)
        # Make cache think it has 2 entries (exceeds max_size of 1)
        cache._cache["skill1:terminal:123"] = {"completed_steps": ["step1"]}
        cache._cache["skill2:terminal:456"] = {"completed_steps": ["step2"]}
        # But _access_times is empty - inconsistent state

        with pytest.raises(ValueError):
            cache._evict_if_needed()
