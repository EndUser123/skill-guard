#!/usr/bin/env python3
"""
Database Connection Management for Breadcrumb Trails
====================================================

Provides SQLite database connection management with:
- WAL mode for concurrent access
- Connection pooling for performance
- Schema initialization and migrations
- Graceful degradation on database unavailability

This module consolidates breadcrumb trail storage into a unified SQLite backend,
replacing the hybrid JSONL+JSON+cache approach.

Example:
    >>> from skill_guard.breadcrumb.database import get_connection, initialize_schema
    >>> conn = get_connection()
    >>> initialize_schema(conn)
    >>> cursor = conn.cursor()
    >>> cursor.execute("SELECT * FROM breadcrumb_trails")
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Final

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default database path (can be overridden via CLAUDE_STATE_DIR env var)
# Uses CLAUDE_STATE_DIR environment variable if set, otherwise falls back to P:/
# Points to the existing diagnostics.db used by Claude Code hooks
_DEFAULT_DB_DIR = Path(os.environ.get("CLAUDE_STATE_DIR", "P:/"))
DEFAULT_DB_PATH: Final = _DEFAULT_DB_DIR / ".claude/hooks/logs/diagnostics/diagnostics.db"

# Connection pool settings
_BUSY_TIMEOUT_MS: Final = int(os.environ.get("CLAUDE_DB_BUSY_TIMEOUT_MS", "5000"))  # 5 seconds default
# WAL mode settings
_JOURNAL_MODE: Final = "wal"

# Schema version for migrations
_SCHEMA_VERSION: Final = 1

# =============================================================================
# CONNECTION POOLING
# =============================================================================

# Thread-local storage for connections
# Key: (thread_id, db_path_str) -> Value: sqlite3.Connection
# This ensures each thread gets one connection per database path
_connection_pool: dict[tuple[int, str], sqlite3.Connection] = {}
_pool_lock = threading.Lock()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection | None:
    """Get a database connection from the pool.

    Creates a new connection if one doesn't exist for the current thread and database path.
    Enables WAL mode and sets busy_timeout for concurrent access.

    Args:
        db_path: Path to database file. Defaults to DEFAULT_DB_PATH.

    Returns:
        SQLite connection or None if database is unavailable

    Example:
        >>> conn = get_connection()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT 1")
        >>> conn.close()
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Get thread ID and db_path string for thread-local storage
    thread_id = threading.get_ident()
    db_path_str = str(db_path)
    pool_key = (thread_id, db_path_str)

    # Check if connection already exists for this thread + database
    with _pool_lock:
        if pool_key in _connection_pool:
            return _connection_pool[pool_key]

    # Create new connection
    try:
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create connection
        conn = sqlite3.connect(str(db_path))

        # Enable WAL mode for concurrent access
        conn.execute(f"PRAGMA journal_mode={_JOURNAL_MODE}")

        # Set busy timeout for write locking (5 seconds)
        conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Store in pool
        with _pool_lock:
            _connection_pool[pool_key] = conn

        return conn

    except (OSError, sqlite3.Error):
        # Graceful degradation: return None if database unavailable
        return None


def close_connection(db_path: Path | None = None) -> None:
    """Close the database connection for the current thread and database path.

    Called automatically during cleanup or when connection is no longer needed.

    Args:
        db_path: Path to database file. If None, closes DEFAULT_DB_PATH connection.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    thread_id = threading.get_ident()
    db_path_str = str(db_path)
    pool_key = (thread_id, db_path_str)

    with _pool_lock:
        if pool_key in _connection_pool:
            conn = _connection_pool[pool_key]
            conn.close()
            del _connection_pool[pool_key]


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version from the database.

    Returns 0 if no schema_versions table exists.
    """
    try:
        cursor = conn.execute("SELECT version FROM schema_versions ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _run_migrations(conn: sqlite3.Connection, from_version: int) -> None:
    """Run schema migrations from from_version to current.

    Args:
        conn: SQLite connection
        from_version: Current schema version in database
    """
    if from_version < 1:
        # Migration v1: Create schema_versions table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_versions (version, applied_at) VALUES (1, ?)",
            (time.time(),),
        )

    # Add future migrations here:
    # if from_version < 2:
    #     ... migration logic ...
    #     conn.execute("INSERT INTO schema_versions ...", (2, time.time()))


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema for breadcrumb trails.

    Creates breadcrumb_trails and breadcrumb_events tables if they don't exist.
    Also creates indexes for performance. Safe to call multiple times.

    Runs schema migrations if database version is older than current.

    Args:
        conn: SQLite connection

    Example:
        >>> conn = get_connection()
        >>> initialize_schema(conn)
    """
    # Run migrations first
    current_version = _get_schema_version(conn)
    if current_version < _SCHEMA_VERSION:
        _run_migrations(conn, current_version)

    # Create breadcrumb_trails table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS breadcrumb_trails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill TEXT NOT NULL,
            terminal_id TEXT NOT NULL,
            run_id TEXT NOT NULL UNIQUE,
            initialized_at REAL NOT NULL,
            workflow_steps TEXT NOT NULL,
            steps TEXT NOT NULL,
            completed_steps TEXT NOT NULL,
            current_step TEXT,
            last_updated REAL NOT NULL,
            tool_count INTEGER DEFAULT 0
        )
        """
    )

    # Create index for terminal-scoped queries
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_terminal
        ON breadcrumb_trails(terminal_id, skill)
        """
    )

    # Create index for run_id lookups
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_run_id
        ON breadcrumb_trails(run_id)
        """
    )

    # Create breadcrumb_events table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS breadcrumb_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trail_id INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            FOREIGN KEY (trail_id) REFERENCES breadcrumb_trails(id) ON DELETE CASCADE
        )
        """
    )

    # Create index for event replay queries
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_breadcrumb_events_trail_timestamp
        ON breadcrumb_events(trail_id, timestamp DESC)
        """
    )


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    "get_connection",
    "close_connection",
    "initialize_schema",
]
