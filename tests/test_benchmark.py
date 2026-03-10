#!/usr/bin/env python3
"""
Performance Benchmarking Suite for Hybrid Logging System
=========================================================

Benchmarks the hybrid logging system against baseline performance metrics.

Tests:
1. Cache hit rates with varying access patterns
2. Log replay performance with different log sizes
3. Memory usage with and without caching
4. Snapshot performance impact
5. Concurrent access performance

Acceptance Criteria:
- Cache hit rate ≥ 80% for repeated reads
- Log replay < 100ms for 1000 entries
- Memory usage < 10MB for active session
- Snapshot creation < 50ms
- Concurrent access maintains integrity

Author: Skill Enforcement v2.0
Date: 2026-03-10
"""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from typing import Any

import pytest

from skill_guard.breadcrumb.log import AppendOnlyBreadcrumbLog
from skill_guard.breadcrumb.tracker import (
    get_breadcrumb,
    set_breadcrumb,
)


class BenchmarkResult:
    """Container for benchmark results."""

    def __init__(self, name: str):
        self.name = name
        self.timings: list[float] = []
        self.memory_samples: list[int] = []

    def add_timing(self, duration_ms: float) -> None:
        """Add a timing measurement."""
        self.timings.append(duration_ms)

    def add_memory(self, bytes_used: int) -> None:
        """Add a memory measurement."""
        self.memory_samples.append(bytes_used)

    def stats(self) -> dict[str, Any]:
        """Get statistics for this benchmark."""
        if not self.timings:
            return {"mean_ms": 0, "median_ms": 0, "min_ms": 0, "max_ms": 0, "samples": 0}

        return {
            "mean_ms": statistics.mean(self.timings),
            "median_ms": statistics.median(self.timings),
            "min_ms": min(self.timings),
            "max_ms": max(self.timings),
            "samples": len(self.timings),
            "memory_mb": statistics.mean(self.memory_samples) / (1024 * 1024) if self.memory_samples else 0,
        }


class TestCachePerformance:
    """Benchmark cache hit rates and performance."""

    def test_cache_hit_rate_repeated_reads(self):
        """Test cache hit rate for repeated reads of same skill."""
        skill = "benchmark_cache_hit"
        cache = BreadcrumbCache()

        # Clear any existing cache
        cache.invalidate(skill)

        # Prime cache with initial write
        cache.set(skill, "research", {"status": "complete"})

        # Perform repeated reads (should all hit cache)
        num_reads = 100
        cache_hits = 0

        for _ in range(num_reads):
            result = cache.get(skill, "research")
            if result is not None:
                cache_hits += 1

        hit_rate = (cache_hits / num_reads) * 100

        # Assert: Cache hit rate should be ≥ 80%
        assert hit_rate >= 80.0, f"Cache hit rate {hit_rate:.1f}% < 80% threshold"

        print(f"\n✓ Cache hit rate: {hit_rate:.1f}% ({cache_hits}/{num_reads} reads)")

        # Cleanup
        cache.invalidate(skill)

    def test_cache_performance_vs_direct_reads(self):
        """Benchmark cache access vs direct log reads."""
        skill = "benchmark_cache_perf"
        log = AppendOnlyBreadcrumbLog(skill)
        cache = BreadcrumbCache()

        # Clear existing data
        log.clear()
        cache.invalidate(skill)

        # Write 100 entries to log
        num_entries = 100
        for i in range(num_entries):
            log.append({"event": "step_complete", "step": f"step_{i}", "data": "x" * 100})

        # Benchmark direct log reads
        direct_read_times = []
        for _ in range(10):
            start = time.perf_counter()
            entries = list(log.replay())
            end = time.perf_counter()
            direct_read_times.append((end - start) * 1000)  # Convert to ms

        # Prime cache
        for entry in entries:
            step = entry.get("step", "")
            cache.set(skill, step, entry)

        # Benchmark cache reads
        cache_read_times = []
        for _ in range(10):
            start = time.perf_counter()
            for i in range(num_entries):
                cache.get(skill, f"step_{i}")
            end = time.perf_counter()
            cache_read_times.append((end - start) * 1000)  # Convert to ms

        direct_mean = statistics.mean(direct_read_times)
        cache_mean = statistics.mean(cache_read_times)
        speedup = direct_mean / cache_mean if cache_mean > 0 else 0

        print(f"\n✓ Direct log read: {direct_mean:.2f}ms")
        print(f"✓ Cache read: {cache_mean:.2f}ms")
        print(f"✓ Speedup: {speedup:.1f}x")

        # Assert: Cache should be faster
        assert cache_mean < direct_mean, "Cache reads should be faster than direct log reads"

        # Cleanup
        log.clear()
        cache.invalidate(skill)

    def test_cache_memory_efficiency(self):
        """Test memory usage of caching system."""
        skill = "benchmark_cache_memory"
        cache = BreadcrumbCache()

        # Start memory tracking
        tracemalloc.start()

        # Baseline memory
        baseline = tracemalloc.get_traced_memory()[0]

        # Add 1000 cached entries
        num_entries = 1000
        for i in range(num_entries):
            cache.set(skill, f"step_{i}", {"step": f"step_{i}", "data": "x" * 100})

        # Measure memory usage
        current = tracemalloc.get_traced_memory()[0]
        memory_used = (current - baseline) / (1024 * 1024)  # Convert to MB

        tracemalloc.stop()

        print(f"\n✓ Memory used for {num_entries} cache entries: {memory_used:.2f}MB")

        # Assert: Memory usage should be reasonable (< 10MB)
        assert memory_used < 10.0, f"Memory usage {memory_used:.2f}MB exceeds 10MB threshold"

        # Cleanup
        cache.invalidate(skill)


class TestLogReplayPerformance:
    """Benchmark log replay performance."""

    def test_replay_performance_small_log(self):
        """Test replay performance for small logs (100 entries)."""
        skill = "benchmark_replay_small"
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Write 100 entries
        num_entries = 100
        for i in range(num_entries):
            log.append({"event": "step_complete", "step": f"step_{i}"})

        # Benchmark replay
        start = time.perf_counter()
        entries = list(log.replay())
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\n✓ Replayed {len(entries)} entries in {duration_ms:.2f}ms")

        # Assert: Should complete quickly
        assert duration_ms < 100, f"Replay took {duration_ms:.2f}ms, exceeds 100ms threshold"
        assert len(entries) == num_entries

        # Cleanup
        log.clear()

    def test_replay_performance_medium_log(self):
        """Test replay performance for medium logs (1000 entries)."""
        skill = "benchmark_replay_medium"
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Write 1000 entries
        num_entries = 1000
        for i in range(num_entries):
            log.append({"event": "step_complete", "step": f"step_{i}", "data": "x" * 50})

        # Benchmark replay
        start = time.perf_counter()
        entries = list(log.replay())
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\n✓ Replayed {len(entries)} entries in {duration_ms:.2f}ms")

        # Assert: Should complete in reasonable time
        assert duration_ms < 100, f"Replay took {duration_ms:.2f}ms, exceeds 100ms threshold"
        assert len(entries) == num_entries

        # Cleanup
        log.clear()

    def test_replay_performance_large_log(self):
        """Test replay performance for large logs (10000 entries)."""
        skill = "benchmark_replay_large"
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Write 10000 entries
        num_entries = 10000
        for i in range(num_entries):
            log.append({"event": "step_complete", "step": f"step_{i}", "data": "x" * 20})

        # Benchmark replay
        start = time.perf_counter()
        entries = list(log.replay())
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\n✓ Replayed {len(entries)} entries in {duration_ms:.2f}ms")
        print(f"  Throughput: {len(entries) / (duration_ms / 1000):.0f} entries/second")

        # Assert: Should complete in reasonable time
        assert duration_ms < 500, f"Replay took {duration_ms:.2f}ms, exceeds 500ms threshold"
        assert len(entries) == num_entries

        # Cleanup
        log.clear()


class TestSnapshotPerformance:
    """Benchmark snapshot creation and loading."""

    def test_snapshot_creation_performance(self):
        """Test snapshot creation performance."""
        skill = "benchmark_snapshot_create"
        state_mgr = BreadcrumbStateManager()
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Create 500 entries in log
        for i in range(500):
            log.append({"event": "step_complete", "step": f"step_{i}", "data": "x" * 100})

        # Benchmark snapshot creation
        start = time.perf_counter()
        snapshot_file = state_mgr._create_snapshot(skill)
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\n✓ Created snapshot in {duration_ms:.2f}ms")
        print(f"  Snapshot file: {snapshot_file.name if snapshot_file else 'None'}")

        # Assert: Should complete quickly
        assert duration_ms < 50, f"Snapshot creation took {duration_ms:.2f}ms, exceeds 50ms threshold"

        # Cleanup
        log.clear()
        if snapshot_file and snapshot_file.exists():
            snapshot_file.unlink()

    def test_snapshot_loading_performance(self):
        """Test snapshot loading performance."""
        skill = "benchmark_snapshot_load"
        state_mgr = BreadcrumbStateManager()
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Create snapshot file manually with 500 entries
        state_dir = state_mgr._get_state_dir()
        snapshot_file = state_dir / f"{skill}_snapshot.json"

        snapshot_data = {
            "timestamp": time.time(),
            "skill": skill,
            "breadcrumbs": {
                f"step_{i}": {
                    "status": "complete",
                    "timestamp": time.time() - i,
                    "metadata": {"index": i}
                }
                for i in range(500)
            }
        }

        snapshot_file.write_text(json.dumps(snapshot_data))

        # Benchmark snapshot loading
        start = time.perf_counter()
        loaded = state_mgr._load_snapshot(skill)
        end = time.perf_counter()

        duration_ms = (end - start) * 1000

        print(f"\n✓ Loaded snapshot in {duration_ms:.2f}ms")
        print(f"  Loaded {len(loaded.get('breadcrumbs', {}))} breadcrumbs")

        # Assert: Should complete quickly
        assert duration_ms < 50, f"Snapshot loading took {duration_ms:.2f}ms, exceeds 50ms threshold"
        assert len(loaded.get("breadcrumbs", {})) == 500

        # Cleanup
        log.clear()
        snapshot_file.unlink(missing_ok=True)


class TestConcurrentAccessPerformance:
    """Benchmark concurrent access performance."""

    def test_concurrent_write_performance(self):
        """Test concurrent write performance with multiple log instances."""
        skill = "benchmark_concurrent_write"

        # Clear existing
        log1 = AppendOnlyBreadcrumbLog(skill)
        log1.clear()

        # Create multiple instances
        log2 = AppendOnlyBreadcrumbLog(skill)
        log3 = AppendOnlyBreadcrumbLog(skill)

        # Benchmark concurrent writes
        start = time.perf_counter()

        for i in range(100):
            log1.append({"event": "step", "step": f"step_{i*3}", "source": "log1"})
            log2.append({"event": "step", "step": f"step_{i*3+1}", "source": "log2"})
            log3.append({"event": "step", "step": f"step_{i*3+2}", "source": "log3"})

        end = time.perf_counter()
        duration_ms = (end - start) * 1000

        # Verify all writes persisted
        entries = list(log1.replay())

        print(f"\n✓ Wrote {len(entries)} entries concurrently in {duration_ms:.2f}ms")

        # Assert: All writes should persist
        assert len(entries) == 300, f"Expected 300 entries, got {len(entries)}"

        # Assert: Should complete in reasonable time
        assert duration_ms < 1000, f"Concurrent writes took {duration_ms:.2f}ms, exceeds 1000ms threshold"

        # Cleanup
        log1.clear()


class TestHybridSystemPerformance:
    """Benchmark complete hybrid logging system."""

    def test_end_to_end_performance(self):
        """Test end-to-end performance of hybrid system."""
        skill = "benchmark_hybrid_e2e"

        # Clear existing
        tracker = BreadcrumbTracker()
        log = AppendOnlyBreadcrumbLog(skill)
        log.clear()

        # Benchmark: Write 100 breadcrumbs through tracker
        start = time.perf_counter()

        for i in range(100):
            set_breadcrumb(skill, f"step_{i}")

        end = time.perf_counter()
        write_duration_ms = (end - start) * 1000

        # Benchmark: Read all breadcrumbs
        start = time.perf_counter()

        for i in range(100):
            get_breadcrumb(skill, f"step_{i}")

        end = time.perf_counter()
        read_duration_ms = (end - start) * 1000

        print(f"\n✓ Wrote 100 breadcrumbs in {write_duration_ms:.2f}ms")
        print(f"  Average: {write_duration_ms / 100:.2f}ms per write")
        print(f"✓ Read 100 breadcrumbs in {read_duration_ms:.2f}ms")
        print(f"  Average: {read_duration_ms / 100:.2f}ms per read")

        # Assert: Performance should be reasonable
        assert write_duration_ms < 1000, f"Writes took {write_duration_ms:.2f}ms, exceeds 1000ms threshold"
        assert read_duration_ms < 500, f"Reads took {read_duration_ms:.2f}ms, exceeds 500ms threshold"

        # Cleanup
        log.clear()

    def test_memory_usage_active_session(self):
        """Test memory usage for active session."""
        skill = "benchmark_hybrid_memory"

        # Clear existing
        log = AppendOnlyBreadcrumbLog(skill)
        log.clear()

        # Start memory tracking
        tracemalloc.start()

        # Baseline memory
        baseline = tracemalloc.get_traced_memory()[0]

        # Simulate active session: 500 operations
        for i in range(500):
            set_breadcrumb(skill, f"step_{i % 50}")  # Cycle through 50 steps

        # Measure memory usage
        current = tracemalloc.get_traced_memory()[0]
        memory_used = (current - baseline) / (1024 * 1024)  # Convert to MB

        tracemalloc.stop()

        print(f"\n✓ Memory used for 500 operations: {memory_used:.2f}MB")

        # Assert: Memory usage should be reasonable (< 10MB)
        assert memory_used < 10.0, f"Memory usage {memory_used:.2f}MB exceeds 10MB threshold"

        # Cleanup
        log.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
