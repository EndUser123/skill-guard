r"""
Characterization test for PERF-006: ValueError from min() on empty _access_times.

These tests CAPTURE CURRENT BEHAVIOR before the bug fix.
The bug: _evict_if_needed() calls min(_access_times) without checking if _access_times is empty.

Location: skill_guard/breadcrumb/cache.py:181
Finding: PERF-006

Run with: pytest P:\\\\packages/skill-guard/tests/test_cache_empty_evict.py -v
"""

import pytest

from skill_guard.breadcrumb.cache import BreadcrumbStateCache


class TestEvictOnEmptyAccessTimes:
    """Tests for _evict_if_needed() behavior when _access_times is empty."""

    def test_evict_if_needed_raises_valueerror_on_empty_access_times(self):
        """
        Test that _evict_if_needed() does NOT raise ValueError when _access_times is empty.

        Given: A BreadcrumbStateCache where len(_cache) > max_size but _access_times is empty
        When:  _evict_if_needed() is called
        Then:  No ValueError is raised (should handle empty _access_times gracefully)

        CURRENT BUG: This test FAILS because min(_access_times) raises ValueError on empty dict.
        After fix: This test should PASS.
        """
        cache = BreadcrumbStateCache(max_size=1)
        # Force inconsistent state: _cache has 2 entries (exceeds max_size of 1)
        # but _access_times is intentionally empty
        cache._cache["test:terminal:123"] = {"completed_steps": ["test"]}
        cache._cache["test2:terminal:456"] = {"completed_steps": ["test2"]}
        # _access_times is intentionally empty

        # Should NOT raise - but currently does due to min() on empty dict
        cache._evict_if_needed()

    def test_evict_if_needed_raises_valueerror_when_cache_exceeds_max_size(self):
        """
        Test that _evict_if_needed() does NOT raise when cache exceeds max_size.

        Given: Cache where len(_cache) > max_size but _access_times is empty
        When:  _evict_if_needed() is called
        Then:  No ValueError is raised

        CURRENT BUG: Raises ValueError from min(empty_dict).
        After fix: Should PASS (evicts gracefully even with empty _access_times).
        """
        cache = BreadcrumbStateCache(max_size=1)
        # Make cache think it has 2 entries (exceeds max_size of 1)
        cache._cache["skill1:terminal:123"] = {"completed_steps": ["step1"]}
        cache._cache["skill2:terminal:456"] = {"completed_steps": ["step2"]}
        # But _access_times is empty - inconsistent state

        # Should NOT raise - but currently does due to min() on empty dict
        cache._evict_if_needed()
