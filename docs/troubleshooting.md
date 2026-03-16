# Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues with the SQLite breadcrumb trail backend. Issues are categorized by severity and component.

## Quick Diagnosis

### Health Check Script

```bash
#!/bin/bash
# Quick health check for breadcrumb system

echo "=== Breadcrumb System Health Check ==="
echo ""

# 1. Check database exists
echo "1. Database existence:"
if [ -f "P:/.claude/hooks/logs/diagnostics/diagnostics.db" ]; then
    echo "   ✓ Database exists"
    ls -lh P:/.claude/hooks/logs/diagnostics/diagnostics.db
else
    echo "   ✗ Database missing"
fi
echo ""

# 2. Check database integrity
echo "2. Database integrity:"
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA integrity_check;"
echo ""

# 3. Check schema
echo "3. Schema verification:"
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "
SELECT 'breadcrumb_trails' as table_name, COUNT(*) FROM breadcrumb_trails
UNION ALL
SELECT 'breadcrumb_events', COUNT(*) FROM breadcrumb_events;
"
echo ""

# 4. Check database size
echo "4. Database size:"
du -sh P:/.claude/hooks/logs/diagnostics/diagnostics.db
echo ""

# 5. Check WAL file
echo "5. WAL file status:"
if [ -f "P:/.claude/hooks/logs/diagnostics/diagnostics.db-wal" ]; then
    echo "   ✓ WAL file exists"
    ls -lh P:/.claude/hooks/logs/diagnostics/diagnostics.db-wal
else
    echo "   ✗ WAL file missing (WAL mode not enabled)"
fi
echo ""

# 6. Check active connections
echo "6. Lock status:"
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA database_list;"
echo ""

echo "=== Health Check Complete ==="
```

**Expected output**:
```
=== Breadcrumb System Health Check ===

1. Database existence:
   ✓ Database exists
-rw-r--r-- 1 user group 2.5M Mar 14 10:30 P:/.claude/hooks/logs/diagnostics/diagnostics.db

2. Database integrity:
ok

3. Schema verification:
breadcrumb_trails|150
breadcrumb_events|1250

4. Database size:
2.5M    P:/.claude/hooks/logs/diagnostics/diagnostics.db

5. WAL file status:
   ✓ WAL file exists
-rw-r--r-- 1 user group 1.2M Mar 14 10:30 P:/.claude/hooks/logs/diagnostics/diagnostics.db-wal

6. Lock status:
0|main|/p/.claude/hooks/logs/diagnostics/diagnostics.db

=== Health Check Complete ===
```

## Common Issues

### Issue 1: Database Locked

**Symptoms**:
- Error: `database is locked`
- Skills hang or timeout
- Operations fail with `sqlite3.OperationalError: database is locked`

**Diagnosis**:
```bash
# Check for active connections
lsof P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Check lock status
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA lock_status;"
```

**Causes**:
1. Multiple terminals writing simultaneously
2. Long-running transaction
3. Previous crash left lock file
4. Another process has database open

**Solutions**:

**Solution 1: Wait and retry**
```bash
# SQLite locks are transient, wait 5 seconds and retry
sleep 5
# Retry operation
```

**Solution 2: Increase busy timeout**
```python
# In database.py, increase _BUSY_TIMEOUT_MS
_BUSY_TIMEOUT_MS = 10000  # 10 seconds (default: 5000)
```

**Solution 3: Close all connections**
```bash
# Close all Claude Code terminals
# Wait 5 seconds
# Retry operation
```

**Solution 4: Remove lock files (last resort)**
```bash
# Check for lock files
ls -la P:/.claude/hooks/logs/diagnostics/diagnostics.db-*

# Remove lock files (DANGER: Only if no active connections)
rm P:/.claude/hooks/logs/diagnostics/diagnostics.db-shm
rm P:/.claude/hooks/logs/diagnostics/diagnostics.db-wal
```

**Prevention**:
- Limit concurrent terminals to ≤ 5
- Use connection pooling
- Keep transactions short
- Enable WAL mode (default)

### Issue 2: Database Corrupted

**Symptoms**:
- Error: `database disk image is malformed`
- Queries return incorrect data
- `PRAGMA integrity_check` fails

**Diagnosis**:
```bash
# Check database integrity
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA integrity_check;"

# Expected output: "ok"
# Any other output indicates corruption
```

**Causes**:
1. Disk full during write
2. Power failure during transaction
3. Concurrent write without WAL mode
4. File system corruption

**Solutions**:

**Solution 1: Rollback migration**
```bash
# Rollback to file-based storage
python -m skill_guard.breadcrumb.migration --rollback

# Delete corrupted database
rm P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Re-run migration
python -m skill_guard.breadcrumb.migration --all
```

**Solution 2: Export and reimport**
```bash
# Export data to SQL
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db .dump > backup.sql

# Create new database
sqlite3 new_diagnostic.db < backup.sql

# Replace old database
mv new_diagnostic.db P:/.claude/hooks/logs/diagnostics/diagnostics.db
```

**Solution 3: Recover data**
```bash
# Attempt recovery (may lose data)
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA wal_checkpoint(TRUNCATE);"

# If still corrupted, dump and recover
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db ".recover" | sqlite3 recovered.db
```

**Prevention**:
- Enable WAL mode (default)
- Ensure sufficient disk space
- Use UPS / battery backup
- Run integrity checks monthly

### Issue 3: Permission Denied

**Symptoms**:
- Error: `unable to open database file`
- Error: `permission denied`
- Operations fail with `OSError`

**Diagnosis**:
```bash
# Check database permissions
ls -la P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Check directory permissions
ls -la P:/.claude/hooks/logs/diagnostics/
```

**Causes**:
1. Database created by different user
2. Read-only file system
3. SELinux / AppArmor restrictions
4. Network drive permissions

**Solutions**:

**Solution 1: Fix permissions**
```bash
# Grant read/write to owner
chmod 644 P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Grant execute on directory
chmod 755 P:/.claude/hooks/logs/diagnostics/
```

**Solution 2: Change ownership**
```bash
# Take ownership of database
sudo chown $USER:$USER P:/.claude/hooks/logs/diagnostics/diagnostics.db
```

**Solution 3: Check file system**
```bash
# Verify file system is writable
touch P:/.claude/hooks/logs/diagnostics/test.txt
rm P:/.claude/hooks/logs/diagnostics/test.txt
```

**Prevention**:
- Run as single user
- Avoid network drives for database
- Check SELinux/AppArmor policies

### Issue 4: Slow Performance

**Symptoms**:
- Queries take > 10ms
- Skills feel sluggish
- High CPU usage

**Diagnosis**:
```bash
# Check database size
du -sh P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Check table size
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "
SELECT 'breadcrumb_trails' as table_name, COUNT(*) FROM breadcrumb_trails
UNION ALL
SELECT 'breadcrumb_events', COUNT(*) FROM breadcrumb_events;
"

# Analyze query plan
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "
EXPLAIN QUERY PLAN
SELECT * FROM breadcrumb_trails WHERE terminal_id = 'term-123';
"
```

**Causes**:
1. Database too large (> 100MB)
2. Missing indexes
3. No cache hits
4. Full table scans

**Solutions**:

**Solution 1: Analyze and optimize**
```bash
# Update query optimizer statistics
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "ANALYZE;"

# Rebuild database
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "VACUUM;"
```

**Solution 2: Archive old data**
```python
# Delete trails older than 90 days
from skill_guard.breadcrumb.sqlite_backend import clear_terminal_trails
import time

cutoff = time.time() - (90 * 24 * 60 * 60)
# Implement archival logic
```

**Solution 3: Check cache hit rate**
```python
# Monitor cache effectiveness
from skill_guard.breadcrumb.cache import BreadcrumbStateCache

cache = BreadcrumbStateCache()
# Log cache hits/misses
```

**Solution 4: Increase busy timeout**
```python
# In database.py, increase _BUSY_TIMEOUT_MS
_BUSY_TIMEOUT_MS = 10000  # 10 seconds
```

**Prevention**:
- Archive old data regularly
- Run VACUUM monthly
- Monitor cache hit rate
- Keep database < 100MB

### Issue 5: Migration Fails

**Symptoms**:
- Error: `Migration failed`
- No data in database after migration
- Validation errors reported

**Diagnosis**:
```bash
# Run validation
python -c "
from skill_guard.breadcrumb.migration import validate_jsonl_files, validate_json_state
from skill_guard.utils.terminal_detection import detect_terminal_id

terminal_id = detect_terminal_id()
print(f'Terminal: {terminal_id}')

jsonl_valid, jsonl_errors = validate_jsonl_files(terminal_id)
print(f'JSONL valid: {jsonl_valid}')
if not jsonl_valid:
    print('Errors:')
    for error in jsonl_errors[:10]:
        print(f'  - {error}')

json_valid, json_errors = validate_json_state(terminal_id)
print(f'JSON valid: {json_valid}')
if not json_valid:
    print('Errors:')
    for error in json_errors[:10]:
        print(f'  - {error}')
"
```

**Causes**:
1. Corrupted JSONL files
2. Invalid JSON state files
3. Missing required fields
4. Permission issues

**Solutions**:

**Solution 1: Fix validation errors**
```bash
# Check specific file
cat P:/.claude/state/breadcrumb_logs_terminal-123/code.jsonl | python -m json.tool

# Fix malformed JSON lines
# (Manual editing required)
```

**Solution 2: Remove corrupted files**
```bash
# Remove problematic files
rm P:/.claude/state/breadcrumb_logs_terminal-123/corrupted.jsonl

# Re-run migration
python -m skill_guard.breadcrumb.migration
```

**Solution 3: Migrate selectively**
```bash
# Migrate only valid terminals
python -m skill_guard.breadcrumb.migration --terminal terminal-123
```

**Solution 4: Skip migration**
```bash
# System will auto-migrate on first use
# No manual intervention required
```

**Prevention**:
- Validate JSON before writing
- Use proper JSON serialization
- Monitor file system health

### Issue 6: WAL File Too Large

**Symptoms**:
- `diagnostics.db-wal` > 100MB
- Database size growing unexpectedly
- Disk space issues

**Diagnosis**:
```bash
# Check WAL file size
ls -lh P:/.claude/hooks/logs/diagnostics/diagnostics.db-wal

# Check WAL checkpoint status
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA wal_checkpoint;"
```

**Causes**:
1. Long-running transactions
2. No checkpointing
3. High write frequency
4. Crash left WAL file

**Solutions**:

**Solution 1: Force checkpoint**
```bash
# Checkpoint WAL file
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

**Solution 2: Restart connections**
```bash
# Close all terminals
# WAL checkpoint runs automatically on close
# Reopen terminals
```

**Solution 3: Adjust auto-checkpoint**
```python
# In database.py, after enabling WAL mode
conn.execute("PRAGMA wal_autocheckpoint = 1000")  # Default: 1000
```

**Prevention**:
- Close connections regularly
- Run manual checkpoint monthly
- Monitor WAL file size

## Advanced Troubleshooting

### Enable SQLite Logging

```python
# In database.py, add logging
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log all SQL statements
conn.set_trace_callback(logger.debug)
```

### Query Performance Analysis

```sql
-- Analyze slow query
EXPLAIN QUERY PLAN
SELECT * FROM breadcrumb_trails
WHERE terminal_id = 'term-123'
ORDER BY last_updated DESC;

-- Check index usage
SELECT * FROM sqlite_master WHERE type = 'index';

-- Check table statistics
PRAGMA table_info(breadcrumb_trails);
PRAGMA index_list(breadcrumb_trails);
PRAGMA index_info(idx_breadcrumb_terminal);
```

### Database Statistics

```sql
-- Check database size
SELECT
    page_count * page_size as 'Database Size (bytes)'
FROM pragma_page_count(), pragma_page_size();

-- Check table sizes
SELECT
    name as 'Table',
    (SELECT COUNT(*) FROM sqlite_master WHERE name = bm.name AND type = 'table') as 'Row Count'
FROM pragma_table_info('breadcrumb_trails') as bm;
```

### Lock Status Monitoring

```sql
-- Check lock status
PRAGMA lock_status;

-- Check busy timeout
PRAGMA busy_timeout;

-- Check journal mode
PRAGMA journal_mode;

-- Check WAL status
PRAGMA wal_checkpoint(PASSIVE);
```

## Emergency Procedures

### Complete System Reset

**Last resort when system is completely broken**:

```bash
#!/bin/bash
# EMERGENCY RESET - Use only as last resort

echo "=== EMERGENCY RESET ==="
echo "This will delete all breadcrumb data and restart from scratch."
echo "Press Ctrl+C to cancel, or Enter to continue."
read

# 1. Close all terminals
echo "Closing all terminals..."
# (Manual step: close all Claude Code terminals)

# 2. Backup existing data
echo "Backing up data..."
mkdir -p P:/.claude/state/emergency_backup_$(date +%Y%m%d_%H%M%S)
cp -r P:/.claude/state/breadcrumb_logs_* P:/.claude/state/emergency_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null
cp -r P:/.claude/state/breadcrumbs_* P:/.claude/state/emergency_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null
cp P:/.claude/hooks/logs/diagnostics/diagnostics.db P:/.claude/state/emergency_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null

# 3. Delete database
echo "Deleting database..."
rm -f P:/.claude/hooks/logs/diagnostics/diagnostics.db
rm -f P:/.claude/hooks/logs/diagnostics/diagnostics.db-*

# 4. Delete old file-based data
echo "Deleting old breadcrumb data..."
rm -rf P:/.claude/state/breadcrumb_logs_*
rm -rf P:/.claude/state/breadcrumbs_*

# 5. System will auto-initialize on next skill use
echo "Reset complete. System will auto-initialize on next skill use."
echo "Backup location: P:/.claude/state/emergency_backup_$(date +%Y%m%d_%H%M%S)/"
```

### Data Recovery

**If database is corrupted but you have backup**:

```bash
# Restore from backup
cp P:/.claude/state/backup_YYYYMMDD/diagnostics.db P:/.claude/hooks/logs/diagnostics/diagnostics.db

# Verify integrity
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "PRAGMA integrity_check;"

# If ok, you're done
# If not, try older backup
```

## Getting Help

### Information to Gather

When reporting issues, collect:

1. **Health check output** (Quick Diagnosis script)
2. **Error messages** (full traceback)
3. **Database size** (`ls -lh diagnostics.db`)
4. **SQLite version** (`sqlite3 --version`)
5. **Python version** (`python --version`)
6. **skill-guard version** (`pip show skill-guard`)
7. **Operating system** (`uname -a`)

### Log Locations

- **Database logs**: `P:/.claude/hooks/logs/`
- **Python logs**: Check terminal output
- **SQLite logs**: Enable with `conn.set_trace_callback()`

### Useful Commands

```bash
# SQLite version
sqlite3 --version

# Python version
python --version

# skill-guard version
pip show skill-guard

# Database schema
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db ".schema"

# Database statistics
sqlite3 P:/.claude/hooks/logs/diagnostics/diagnostics.db "SELECT COUNT(*) FROM breadcrumb_trails;"
```

## Prevention Checklist

Use this checklist to prevent issues:

- [ ] Enable WAL mode (default)
- [ ] Set busy timeout to 5000ms (default)
- [ ] Run integrity check monthly
- [ ] Run VACUUM monthly
- [ ] Archive old trails (> 90 days)
- [ ] Monitor database size (< 100MB)
- [ ] Monitor WAL file size (< 10MB)
- [ ] Keep connections closed when not in use
- [ ] Limit concurrent terminals (≤ 5)
- [ ] Backup database weekly
- [ ] Test restore procedure monthly
- [ ] Monitor cache hit rate (> 80%)
- [ ] Check disk space (keep 1GB free)
- [ ] Use connection pooling (default)
- [ ] Validate JSON before writing

## Summary

Most issues can be resolved with:

1. **Wait and retry** (transient locks)
2. **Close all terminals** (connection cleanup)
3. **Run integrity check** (detect corruption)
4. **Rollback migration** (restore file-based)
5. **Emergency reset** (last resort)

**Prevention is better than cure**: Monitor database health, archive old data, run maintenance monthly.
