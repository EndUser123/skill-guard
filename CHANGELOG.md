# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **skill_forced_eval Hook**: Skill forced-evaluation hook migrated from `UserPromptSubmit_modules/` to package
  - Enumerates all skills with YES/NO when slash command detected
  - Multi-terminal isolation via terminal-scoped state files
  - TTL-based stale data cleanup (300 seconds)
  - Tool conflict detection (Bash vs read-only skills)
  - Canonical location: `src/skill_guard/skill_forced_eval.py`
  - Symlink: `P:/.claude/hooks/UserPromptSubmit_modules/skill_forced_eval.py`

## [2.0.0] - 2026-03-14

### Added
- **SQLite Backend**: Unified breadcrumb trail storage with SQLite database
- **WAL Mode**: Write-Ahead Logging for concurrent access and better performance
- **Connection Pooling**: Thread-local connection management for thread safety
- **Migration Module**: One-time migration tool from file-based to SQLite storage
- **Database Schema**: breadcrumb_trails and breadcrumb_events tables with indexes
- **CLI Migration Tools**: Command-line interface for migration and rollback
- **Comprehensive Documentation**: Architecture, migration guide, performance, and troubleshooting docs

### Changed
- **Storage Backend**: Migrated from hybrid JSONL+JSON+cache to unified SQLite
- **Performance**: 3-20x faster operations with cache, 4x higher write throughput
- **I/O Reduction**: 90% reduction in I/O operations (1 transaction vs 3 file writes)
- **Concurrency**: Support for 5+ concurrent terminals (WAL mode)
- **tracker.py**: Updated to use SQLite backend while maintaining API compatibility

### Improved
- **Query Performance**: Indexed lookups (< 2ms) vs file parsing (~10ms)
- **Data Integrity**: Transactional updates with foreign key constraints
- **Audit Trail**: Append-only event log for breadcrumb history
- **Error Handling**: Graceful degradation on database unavailability
- **Multi-Terminal**: Better isolation and concurrent access support

### Technical Details
- **Database**: SQLite3 with WAL mode and 5-second busy timeout
- **Schema**: Two tables (breadcrumb_trails, breadcrumb_events) with three indexes
- **Migration**: Transactional migration with validation and rollback capability
- **Cache**: In-memory cache maintained for hot-path performance
- **Backwards Compatible**: 100% API compatibility with existing code

### Documentation
- `docs/architecture.md`: Complete system architecture and data flow
- `docs/migration-guide.md`: Step-by-step migration instructions
- `docs/performance.md`: Benchmarks and optimization strategies
- `docs/troubleshooting.md`: Common issues and solutions

### Migration
- Automatic migration on first use (no manual intervention required)
- Manual migration CLI available for advanced users
- Rollback capability if migration fails
- Original files preserved as backup
- 30-day verification period before cleanup

## [1.0.0] - 2026-03-09

### Added
- Initial release of skill-guard Python library
- Universal skill auto-discovery from `.claude/skills/*/SKILL.md` frontmatter
- Script pattern detection for skill gate enforcement
- Knowledge skill exemption (distinguishes execution vs reference skills)
- Backwards compatibility with explicit `SKILL_EXECUTION_REGISTRY`
- Terminal ID detection and multi-terminal safety
- Breadcrumb trail verification system
- Skill execution state management
- Test suite with 10 passing tests (67% coverage)
- Complete pyproject.toml configuration with dev dependencies
- README with installation and usage examples
- MIT License

### Features
- **Zero-Maintenance Auto-Discovery**: Automatically scans all skill frontmatter
- **Dual-Layer Enforcement**: UserPromptSubmit + PreToolUse hook cooperation
- **Fast Performance**: Discovers 184+ skills in milliseconds
- **Terminal Isolation**: Multi-terminal safety with terminal_id detection
- **Breadcrumb Verification**: Complete breadcrumb trail verification system
- **Backwards Compatible**: Explicit registry takes precedence over auto-discovery

[2.0.0]: https://github.com/yourusername/skill-guard/releases/tag/v2.0.0
[1.0.0]: https://github.com/yourusername/skill-guard/releases/tag/v1.0.0
