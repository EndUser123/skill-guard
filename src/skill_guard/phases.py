"""
phases.py
=========

Phase machine constants for skill execution state.
Extracted from skill_execution_state.py for clean separation.
"""

from __future__ import annotations

# Phase machine states (for workflow_completion_tracker compatibility)
_PHASE_PENDING = "pending"
_PHASE_LOADED = "loaded"
_PHASE_EXECUTING = "executing"
_PHASE_COMPLETE = "complete"
_PHASE_STALE = "stale"

# Valid phase transitions: from_state -> [allowed_to_states]
VALID_TRANSITIONS: dict[str, list[str]] = {
    _PHASE_PENDING: [_PHASE_LOADED],
    _PHASE_LOADED: [_PHASE_EXECUTING, _PHASE_STALE],
    _PHASE_EXECUTING: [_PHASE_COMPLETE, _PHASE_STALE],
    _PHASE_COMPLETE: [],  # Terminal state
    _PHASE_STALE: [],  # Terminal state
}

# Default stale timeout in seconds
DEFAULT_STALE_TIMEOUT = 300