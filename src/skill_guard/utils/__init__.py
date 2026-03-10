"""
Utilities for skill-guard package.

This module provides shared utilities for terminal detection and other
common functionality used across the skill-guard package.
"""

from .terminal_detection import (
    SOURCE_ENV,
    SOURCE_FALLBACK,
    TERMINAL_ENV_VARS,
    _normalize_id,
    detect_terminal_id,
    detect_terminal_id_with_source,
)

__all__ = [
    "detect_terminal_id",
    "detect_terminal_id_with_source",
    "SOURCE_ENV",
    "SOURCE_FALLBACK",
    "TERMINAL_ENV_VARS",
    "_normalize_id",
]
