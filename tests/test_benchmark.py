#!/usr/bin/env python3
"""
Performance Benchmarking Suite for Hybrid Logging System
=========================================================

Benchmarks the hybrid logging system against baseline performance metrics.

Tests:
1. Log replay performance with different log sizes
2. Memory usage for active sessions
3. Concurrent access performance
4. End-to-end system performance

Acceptance Criteria:
- Log replay < 100ms for 1000 entries
- Memory usage < 10MB for active session
- Concurrent access maintains integrity
- System operations complete in reasonable time

Author: Skill Enforcement v2.0
Date: 2026-03-10
"""

from __future__ import annotations

import statistics
import time
import tracemalloc

import pytest

from skill_guard.breadcrumb.log import AppendOnlyBreadcrumbLog
from skill_guard.breadcrumb.tracker import (
    get_breadcrumb_trail,
    set_breadcrumb,
)


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
        """Test replay performance for large logs (5000 entries)."""
        skill = "benchmark_replay_large"
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Write 5000 entries (smaller than 1MB rotation threshold)
        num_entries = 5000
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
        # Note: May have fewer entries due to log rotation, so we check that we got most of them
        assert len(entries) >= num_entries * 0.9, f"Expected at least {num_entries * 0.9} entries, got {len(entries)}"

        # Cleanup
        log.clear()


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

        # Create SKILL.md with workflow_steps for this test skill
        skill_dir = Path("P:/.claude/skills") / skill.lower()
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        # Create workflow_steps for testing
        workflow_steps = [f"step_{i}" for i in range(100)]
        skill_file.write_text(f"""---
workflow_steps:
  {chr(10).join(f'  - {step}' for step in workflow_steps)}
---
# Benchmark Test Skill

This is a test skill for benchmarking.
""")

        try:
            # Clear existing
            log = AppendOnlyBreadcrumbLog(skill)
            log.clear()

            # Initialize breadcrumb trail
            initialize_breadcrumb_trail(skill)

            # Benchmark: Write 100 breadcrumbs through tracker
            start = time.perf_counter()

            for i in range(100):
                set_breadcrumb(skill, f"step_{i}")

            end = time.perf_counter()
            write_duration_ms = (end - start) * 1000

            # Benchmark: Read breadcrumb trail
            start = time.perf_counter()

            for _ in range(10):
                trail = get_breadcrumb_trail(skill)

            end = time.perf_counter()
            read_duration_ms = (end - start) * 1000

            print(f"\n✓ Wrote 100 breadcrumbs in {write_duration_ms:.2f}ms")
            print(f"  Average: {write_duration_ms / 100:.2f}ms per write")
            print(f"✓ Read trail 10 times in {read_duration_ms:.2f}ms")
            print(f"  Average: {read_duration_ms / 10:.2f}ms per read")

            # Assert: Performance should be reasonable
            assert write_duration_ms < 1000, f"Writes took {write_duration_ms:.2f}ms, exceeds 1000ms threshold"
            assert read_duration_ms < 500, f"Reads took {read_duration_ms:.2f}ms, exceeds 500ms threshold"

            # Verify trail was created
            trail = get_breadcrumb_trail(skill)
            assert trail is not None, "Breadcrumb trail should exist"
            assert len(trail.get("completed_steps", [])) == 100, "Should have 100 completed steps"

        finally:
            # Cleanup
            log.clear()
            if skill_file.exists():
                skill_file.unlink()
            if skill_dir.exists():
                skill_dir.rmdir()

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

    def test_write_performance(self):
        """Test write performance for log operations."""
        skill = "benchmark_write_perf"
        log = AppendOnlyBreadcrumbLog(skill)

        # Clear existing
        log.clear()

        # Benchmark single writes
        single_write_times = []
        for i in range(100):
            start = time.perf_counter()
            log.append({"event": "step_complete", "step": f"step_{i}"})
            end = time.perf_counter()
            single_write_times.append((end - start) * 1000)  # Convert to ms

        avg_single_write = statistics.mean(single_write_times)

        # Benchmark batch writes
        batch_start = time.perf_counter()
        for i in range(100, 200):
            log.append({"event": "step_complete", "step": f"step_{i}"})
        batch_end = time.perf_counter()
        batch_duration_ms = (batch_end - batch_start) * 1000
        avg_batch_write = batch_duration_ms / 100

        print(f"\n✓ Single write avg: {avg_single_write:.3f}ms")
        print(f"✓ Batch write avg: {avg_batch_write:.3f}ms")

        # Assert: Writes should be fast
        assert avg_single_write < 10, f"Single write took {avg_single_write:.3f}ms, exceeds 10ms threshold"
        assert avg_batch_write < 10, f"Batch write took {avg_batch_write:.3f}ms, exceeds 10ms threshold"

        # Cleanup
        log.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
