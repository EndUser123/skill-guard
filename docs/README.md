# Documentation Index

Welcome to the skill-guard documentation. This library provides skill execution enforcement with breadcrumb-based verification for Claude Code hooks.

## Quick Start

1. **New Users**: Read the main [README](../README.md)
2. **Upgrading to v2.0**: Read the [Migration Guide](migration-guide.md)
3. **Troubleshooting**: Check the [Troubleshooting Guide](troubleshooting.md)

## Documentation

### [Architecture](architecture.md)

**Complete system architecture and design documentation.**

- System overview and architecture diagrams
- Component descriptions (database, backend, migration, cache)
- Database schema and data flow
- Concurrency model and multi-terminal safety
- Security considerations
- Future enhancements

**Best for**: Understanding how the system works internally.

### [Migration Guide](migration-guide.md)

**Step-by-step instructions for migrating to SQLite backend.**

- Pre-migration checklist
- Automatic vs manual migration
- Validation and verification
- Rollback procedures
- Post-migration cleanup
- FAQ and troubleshooting

**Best for**: Upgrading from v1.0 to v2.0.

### [Performance](performance.md)

**Benchmarks, optimization strategies, and performance tuning.**

- Operation latency comparisons
- Throughput metrics
- Cache optimization
- Concurrency limits
- Query optimization
- Performance monitoring
- Scalability analysis

**Best for**: Optimizing system performance and monitoring.

### [Troubleshooting](troubleshooting.md)

**Common issues, diagnosis, and solutions.**

- Quick health check script
- Common issues (database locked, corrupted, permissions)
- Advanced troubleshooting
- Emergency procedures
- Prevention checklist

**Best for**: Resolving issues and system maintenance.

## Version Information

- **Current Version**: 2.0.0
- **Release Date**: 2026-03-14
- **Major Changes**: SQLite backend, WAL mode, migration tools

## Key Features (v2.0)

- **SQLite Backend**: Unified database storage with WAL mode
- **Performance**: 3-20x faster operations with caching
- **Concurrency**: Support for 5+ concurrent terminals
- **Migration**: Automatic and reversible migration
- **Documentation**: Comprehensive guides and references

## Related Files

- [CHANGELOG](../CHANGELOG.md) - Version history and changes
- [README](../README.md) - Main project documentation
- [plan-sqlite-backend.md](../plan-sqlite-backend.md) - Implementation plan

## Support

For issues or questions:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review the [FAQ](migration-guide.md#faq)
3. Check logs: `P:/.claude/hooks/logs/`
4. Open an issue on GitHub

## Documentation Structure

```
docs/
├── README.md                  # This file (documentation index)
├── architecture.md            # System architecture and design
├── migration-guide.md         # Migration instructions
├── performance.md             # Performance characteristics
└── troubleshooting.md         # Troubleshooting procedures
```

## Quick Reference

### Common Commands

```bash
# Check database health
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA integrity_check;"

# Migrate to SQLite
python -m skill_guard.breadcrumb.migration --all

# Rollback migration
python -m skill_guard.breadcrumb.migration --rollback

# Check database size
du -sh P:/.claude/hooks/logs/diagnostics/diagnostics.db
```

### Key Files

- **Database**: `P:/.claude/hooks/logs/diagnostics/diagnostics.db`
- **Logs**: `P:/.claude/hooks/logs/`
- **State**: `P:/.claude/state/`

### Performance Targets

- Query latency: < 10ms (p95)
- Lock wait time: < 100ms (p95)
- Cache hit rate: > 80%
- Database size: < 100MB

## Documentation Metrics

- **Total Documentation**: 2,442 lines
- **Architecture**: 424 lines
- **Migration Guide**: 458 lines
- **Performance**: 438 lines
- **Troubleshooting**: 656 lines

## Summary

The skill-guard v2.0 documentation provides comprehensive coverage of:

- ✅ System architecture and design
- ✅ Migration procedures and rollback
- ✅ Performance characteristics and optimization
- ✅ Troubleshooting and maintenance
- ✅ Security and monitoring
- ✅ FAQ and common issues

All documentation is maintained in Markdown format for easy reading and contribution.
