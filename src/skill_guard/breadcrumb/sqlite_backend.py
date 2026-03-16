#!/usr/bin/env python3
"""
SQLite Backend for Breadcrumb Trails
=====================================

SQLite-based breadcrumb operations that replace file-based operations.

Provides:
- create_trail(): Create new breadcrumb trail
- update_trail(): Update existing trail
- append_event(): Append event to audit log
- get_active_trails(): Query trails by terminal

API compatible with existing tracker.py operations.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from skill_guard.breadcrumb.database import get_connection

# =============================================================================
# CRUD OPERATIONS
# =============================================================================


def create_trail(
    db_path: Path,
    skill: str,
    terminal_id: str,
    workflow_steps: list[dict[str, Any]],
    steps: dict[str, dict[str, Any]],
) -> str:
    """Create a new breadcrumb trail.

    Args:
        db_path: Path to database file
        skill: Skill name
        terminal_id: Terminal identifier
        workflow_steps: List of workflow step definitions
        steps: Dictionary mapping step IDs to metadata

    Returns:
        Unique run_id for the trail

    Example:
        >>> run_id = create_trail(
        ...     db_path=Path("breadcrumbs.db"),
        ...     skill="code",
        ...     terminal_id="terminal-123",
        ...     workflow_steps=[{"id": "analyze", "kind": "execution"}],
        ...     steps={"analyze": {"kind": "execution", "status": "pending"}},
        ... )
    """
    # Generate unique run_id
    run_id = str(uuid.uuid4())
    current_time = time.time()

    # Serialize data for storage
    workflow_steps_json = json.dumps(workflow_steps)
    steps_json = json.dumps(steps)
    completed_steps_json = json.dumps([])

    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Insert trail
    cursor.execute(
        """
        INSERT INTO breadcrumb_trails (
            skill, terminal_id, run_id, initialized_at,
            workflow_steps, steps, completed_steps,
            current_step, last_updated, tool_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            skill,
            terminal_id,
            run_id,
            current_time,
            workflow_steps_json,
            steps_json,
            completed_steps_json,
            None,  # current_step
            current_time,  # last_updated
            0,  # tool_count
        ),
    )

    # Get trail_id for event logging
    trail_id = cursor.lastrowid

    # Append initialization event
    cursor.execute(
        """
        INSERT INTO breadcrumb_events (
            trail_id, timestamp, event_type, event_data
        ) VALUES (?, ?, ?, ?)
        """,
        (
            trail_id,
            current_time,
            "trail_initialized",
            json.dumps({"run_id": run_id, "workflow_steps": workflow_steps}),
        ),
    )

    # Commit transaction
    conn.commit()

    return run_id


def update_trail(
    db_path: Path,
    run_id: str,
    completed_steps: list[str],
    current_step: str | None,
    steps: dict[str, dict[str, Any]],
) -> None:
    """Update an existing breadcrumb trail.

    Args:
        db_path: Path to database file
        run_id: Unique run identifier
        completed_steps: List of completed step IDs
        current_step: Current step ID (or None)
        steps: Updated steps dictionary with metadata

    Example:
        >>> update_trail(
        ...     db_path=Path("breadcrumbs.db"),
        ...     run_id="some-uuid",
        ...     completed_steps=["analyze"],
        ...     current_step="refactor",
        ...     steps={"analyze": {"status": "done", "evidence": {}}},
        ... )
    """
    current_time = time.time()

    # Serialize data for storage
    completed_steps_json = json.dumps(completed_steps)
    steps_json = json.dumps(steps)

    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Get trail_id for event logging
    cursor.execute("SELECT id FROM breadcrumb_trails WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    if not row:
        return  # Trail not found
    trail_id = row[0]

    # Update trail
    cursor.execute(
        """
        UPDATE breadcrumb_trails
        SET completed_steps = ?, current_step = ?, steps = ?, last_updated = ?
        WHERE run_id = ?
        """,
        (
            completed_steps_json,
            current_step,
            steps_json,
            current_time,
            run_id,
        ),
    )

    # Append step_complete event if current_step is provided
    if current_step:
        cursor.execute(
            """
            INSERT INTO breadcrumb_events (
                trail_id, timestamp, event_type, event_data
            ) VALUES (?, ?, ?, ?)
            """,
            (
                trail_id,
                current_time,
                "step_complete",
                json.dumps({"step": current_step}),
            ),
        )

    # Commit transaction
    conn.commit()


def append_event(
    db_path: Path,
    trail_id: int,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> None:
    """Append an event to the breadcrumb audit log.

    Args:
        db_path: Path to database file
        trail_id: Trail ID (from breadcrumb_trails table)
        event_type: Type of event (e.g., "step_complete", "trail_initialized")
        event_data: Optional event data dictionary

    Example:
        >>> append_event(
        ...     db_path=Path("breadcrumbs.db"),
        ...     trail_id=123,
        ...     event_type="step_complete",
        ...     event_data={"step": "analyze", "evidence": {}},
        ... )
    """
    current_time = time.time()

    # Serialize event data
    event_data_json = json.dumps(event_data) if event_data else None

    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Insert event
    cursor.execute(
        """
        INSERT INTO breadcrumb_events (
            trail_id, timestamp, event_type, event_data
        ) VALUES (?, ?, ?, ?)
        """,
        (
            trail_id,
            current_time,
            event_type,
            event_data_json,
        ),
    )

    # Commit transaction
    conn.commit()


def get_active_trails(db_path: Path, terminal_id: str) -> list[dict[str, Any]]:
    """Get all active breadcrumb trails for a terminal.

    Args:
        db_path: Path to database file
        terminal_id: Terminal identifier

    Returns:
        List of trail dictionaries

    Example:
        >>> trails = get_active_trails(
        ...     db_path=Path("breadcrumbs.db"),
        ...     terminal_id="terminal-123",
        ... )
        >>> for trail in trails:
        ...     print(f"Skill: {trail['skill']}, Run: {trail['run_id']}")
    """
    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Query trails for terminal
    cursor.execute(
        """
        SELECT
            id, skill, terminal_id, run_id, initialized_at,
            workflow_steps, steps, completed_steps,
            current_step, last_updated, tool_count
        FROM breadcrumb_trails
        WHERE terminal_id = ?
        ORDER BY last_updated DESC
        """,
        (terminal_id,),
    )

    # Convert rows to dictionaries
    trails = []
    for row in cursor.fetchall():
        trail = {
            "id": row[0],
            "skill": row[1],
            "terminal_id": row[2],
            "run_id": row[3],
            "initialized_at": row[4],
            "workflow_steps": json.loads(row[5]),
            "steps": json.loads(row[6]),
            "completed_steps": json.loads(row[7]),
            "current_step": row[8],
            "last_updated": row[9],
            "tool_count": row[10],
        }
        trails.append(trail)

    return trails


def get_trail_by_run_id(db_path: Path, run_id: str) -> dict[str, Any] | None:
    """Get a breadcrumb trail by run_id.

    Args:
        db_path: Path to database file
        run_id: Unique run identifier

    Returns:
        Trail dictionary or None if not found

    Example:
        >>> trail = get_trail_by_run_id(
        ...     db_path=Path("breadcrumbs.db"),
        ...     run_id="some-uuid",
        ... )
    """
    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Query trail by run_id
    cursor.execute(
        """
        SELECT
            id, skill, terminal_id, run_id, initialized_at,
            workflow_steps, steps, completed_steps,
            current_step, last_updated, tool_count
        FROM breadcrumb_trails
        WHERE run_id = ?
        """,
        (run_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    # Convert to dictionary
    trail = {
        "id": row[0],
        "skill": row[1],
        "terminal_id": row[2],
        "run_id": row[3],
        "initialized_at": row[4],
        "workflow_steps": json.loads(row[5]),
        "steps": json.loads(row[6]),
        "completed_steps": json.loads(row[7]),
        "current_step": row[8],
        "last_updated": row[9],
        "tool_count": row[10],
    }

    return trail


def delete_trail(db_path: Path, run_id: str) -> bool:
    """Delete a breadcrumb trail by run_id.

    Args:
        db_path: Path to database file
        run_id: Unique run identifier

    Returns:
        True if trail was deleted, False if not found

    Example:
        >>> deleted = delete_trail(
        ...     db_path=Path("breadcrumbs.db"),
        ...     run_id="some-uuid",
        ... )
    """
    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Delete trail (cascade will delete events)
    cursor.execute("DELETE FROM breadcrumb_trails WHERE run_id = ?", (run_id,))

    # Commit transaction
    conn.commit()

    # Return True if row was deleted
    return cursor.rowcount > 0


def clear_terminal_trails(db_path: Path, terminal_id: str) -> int:
    """Clear all breadcrumb trails for a terminal.

    Args:
        db_path: Path to database file
        terminal_id: Terminal identifier

    Returns:
        Number of trails deleted

    Example:
        >>> count = clear_terminal_trails(
        ...     db_path=Path("breadcrumbs.db"),
        ...     terminal_id="terminal-123",
        ... )
        >>> print(f"Cleared {count} trails")
    """
    # Get connection
    conn = get_connection(db_path)
    if conn is None:
        raise RuntimeError("Database connection failed")

    cursor = conn.cursor()

    # Delete trails for terminal (cascade will delete events)
    cursor.execute(
        "DELETE FROM breadcrumb_trails WHERE terminal_id = ?",
        (terminal_id,),
    )

    # Commit transaction
    conn.commit()

    # Return count of deleted rows
    return cursor.rowcount
