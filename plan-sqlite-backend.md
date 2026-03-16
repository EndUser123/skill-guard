# Plan: Unified SQLite Backend for Breadcrumb Trails

## Overview

Migrate breadcrumb trails from hybrid JSONL+JSON+cache to unified SQLite backend with WAL mode, consolidating with existing diagnostics.db infrastructure. This eliminates file system litter, reduces I/O operations, and enables complex verification queries.

## Architecture

### Components

**Module: skill_guard/breadcrumb/database.py** (NEW)
- Database connection management with WAL mode
- Schema initialization and migrations
- Connection pooling for concurrent access
- Fallback to existing file system during transition

**Module: skill_guard/breadcrumb/sqlite_backend.py** (NEW)
- SQLite-based breadcrumb operations
- Replaces AppendOnlyBreadcrumbLog and JSON file operations
- Maintains BreadcrumbStateCache for hot-path performance
- Provides same API as existing tracker.py

**Module: skill_guard/breadcrumb/migration.py** (NEW)
- One-time migration tool for existing JSONL data
- Migrates JSONL logs to breadcrumb_events table
- Migrates JSON state files to breadcrumb_trails table
- Validation and rollback capabilities

**Modified: tracker.py**
- Replace file operations with SQLite backend calls
- Keep existing API surface (backward compatible)
- Add database initialization check

### Data Flow

```
Skill Invocation
    ↓
initialize_breadcrumb_trail()
    → sqlite_backend.create_trail() [INSERT to breadcrumb_trails]
    → cache.update_state() [in-memory cache]
    ↓
Tool Execution (PostToolUse hook)
    ↓
set_breadcrumb()
    → sqlite_backend.update_trail() [UPSERT breadcrumb_trails]
    → sqlite_backend.append_event() [INSERT to breadcrumb_events]
    → cache.update_state() [in-memory cache]
    ↓
Verification Query
    ↓
get_active_breadcrumb_trails()
    → sqlite_backend.get_active_trails() [SELECT with terminal filter]
    → cache.get_state() [if available, fallback to DB]
```

### Database Schema

```sql
-- Main breadcrumb trails table
CREATE TABLE IF NOT EXISTS breadcrumb_trails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill TEXT NOT NULL,
    terminal_id TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    initialized_at REAL NOT NULL,
    workflow_steps TEXT NOT NULL,  -- JSON array
    steps TEXT NOT NULL,  -- JSON dict (step_id -> metadata)
    completed_steps TEXT NOT NULL,  -- JSON array
    current_step TEXT,
    last_updated REAL NOT NULL,
    tool_count INTEGER DEFAULT 0
);

-- Index for terminal-scoped queries
CREATE INDEX IF NOT EXISTS idx_breadcrumb_terminal
    ON breadcrumb_trails(terminal_id, skill);

-- Index for run_id lookups
CREATE INDEX IF NOT EXISTS idx_breadcrumb_run_id
    ON breadcrumb_trails(run_id);

-- Audit trail events (append-only)
CREATE TABLE IF NOT EXISTS breadcrumb_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trail_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,  -- 'step_complete', 'trail_initialized'
    event_data TEXT,  -- JSON
    FOREIGN KEY (trail_id) REFERENCES breadcrumb_trails(id) ON DELETE CASCADE
);

-- Index for event replay queries
CREATE INDEX IF NOT EXISTS idx_breadcrumb_events_trail_timestamp
    ON breadcrumb_events(trail_id, timestamp DESC);
```

## Error Handling

**Database Connection Failures:**
- Graceful degradation to existing file system
- Retry logic with exponential backoff (max 3 attempts)
- Error logging for diagnosis

**Migration Failures:**
- Validation before migration (check JSONL file integrity)
- Transactional migration (all-or-nothing)
- Rollback capability if migration fails

**Concurrent Access:**
- SQLite WAL mode allows concurrent readers
- Write locking with busy_timeout (5 seconds)
- Connection pooling to reduce contention

## Test Strategy

### Unit Tests

**database.py** (NEW)
- Test database initialization
- Test schema creation and migrations
- Test connection pooling
- Test WAL mode configuration

**sqlite_backend.py** (NEW)
- Test create_trail() operation
- Test update_trail() operation
- Test append_event() operation
- Test get_active_trails() query
- Test cache integration

**migration.py** (NEW)
- Test JSONL to breadcrumb_events migration
- Test JSON to breadcrumb_trails migration
- Test migration validation
- Test rollback capability

### Integration Tests

**tracker.py compatibility**
- Test existing API still works
- Test backward compatibility with cache
- Test terminal isolation preserved
- Test performance baseline (< 50ms per operation)

**Migration end-to-end**
- Test full migration with sample data
- Test data integrity after migration
- Test rollback on failure

## Standards Compliance

**Python 2025+ standards (//p):**
- Type hints for all functions
- Async/await for database operations (if needed)
- Context managers for resource management
- Logging with structured format

**Universal principles:**
- DRY: Reuse database connection code
- Separation of concerns: Database layer separate from business logic
- YAGNI: Only implement needed queries
- Testing: Comprehensive test coverage

## Ramifications

### Breaking Changes

**None** - API surface maintained, backward compatible during transition

### Data Migration

**Required:** One-time migration of existing JSONL and JSON files
- Migration tool provided (opt-in via CLI)
- Existing files remain as backup
- No automatic deletion (manual cleanup after verification)

### Performance Impact

**Expected improvements:**
- Reduced I/O (single database connection vs 3 file writes)
- Faster queries (indexed lookups vs file parsing)
- Better concurrency (WAL mode allows parallel reads)

**Expected regression risk:**
- Database lock contention under high load (mitigated by WAL mode)
- Migration performance for large datasets (mitigated by batching)

### Backwards Compatibility

**Maintained:**
- Existing tracker.py API unchanged
- BreadcrumbStateCache still used for hot-path
- Fallback to file system if database unavailable

**Migration path:**
- Phase 1: Database layer with fallback
- Phase 2: Gradual migration of active terminals
- Phase 3: Deprecation of file system backend

## Pre-Mortem Analysis

**Failure Mode #1: Database lock contention**
- **Root cause:** Multiple terminals writing to same database file
- **Probability:** Medium (SQLite WAL mode reduces but doesn't eliminate)
- **Prevention:** WAL mode enabled, busy_timeout configured, write batching
- **Detection:** Monitor lock wait time, log slow queries
- **Test:** Concurrent write test with multiple terminals

**Failure Mode #2: Migration data loss**
- **Root cause:** JSONL parsing error or incomplete migration
- **Probability:** Low (validation and rollback in place)
- **Prevention:** Pre-migration validation, transactional migration, backup preservation
- **Detection:** Compare record counts before/after, validate data integrity
- **Test:** Migration test with sample data, verify rollback

**Failure Mode #3: Performance regression**
- **Root cause:** SQLite queries slower than in-memory cache
- **Probability:** Low (cache layer maintained)
- **Prevention:** Keep BreadcrumbStateCache for hot-path, indexed queries, connection pooling
- **Detection:** Performance baseline monitoring, query timing logs
- **Test:** Performance benchmark before/after, < 50ms target

## Observability Planning

**Metrics to track:**
- Database query latency (ms)
- Lock wait time (ms)
- Migration success rate (%)
- Cache hit rate (%)

**Alerts:**
- Database connection failures (alert if > 3 in 1 minute)
- Slow queries (> 100ms)
- Migration failures (immediate alert)

**Diagnosis paths:**
- Check SQLite WAL file size
- Monitor database locks via `PRAGMA database_list`
- Query plan analysis via `EXPLAIN QUERY PLAN`
- Check cache effectiveness via hit/miss metrics

## Implementation Tasks

### TASK-001: Create database.py module
- Database connection management
- Schema initialization
- Connection pooling
- WAL mode configuration

### TASK-002: Create sqlite_backend.py module
- SQLite-based breadcrumb operations
- API compatibility with tracker.py
- Cache integration
- Event logging

### TASK-003: Create migration.py module
- JSONL to breadcrumb_events migration
- JSON to breadcrumb_trails migration
- Validation and rollback
- CLI interface

### TASK-004: Update tracker.py
- Replace file operations with SQLite backend
- Maintain existing API surface
- Add database initialization check
- Keep cache layer

### TASK-005: Write comprehensive tests
- Unit tests for all new modules
- Integration tests for tracker.py compatibility
- Migration tests with sample data
- Performance benchmarks

### TASK-006: Update documentation
- Document new architecture
- Migration guide for users
- Performance characteristics
- Troubleshooting guide
