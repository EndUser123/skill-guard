"""
Utilities for skill-guard package.

This module provides shared utilities for terminal detection and other
common functionality used across the skill-guard package.
"""

from .terminal_detection import (
    SOURCE_CONSOLE,
    SOURCE_ENV,
    SOURCE_FALLBACK,
    TERMINAL_ENV_VARS,
    detect_terminal_id,
    detect_terminal_id_with_source,
)

from .terminal_id import normalize_terminal_id

__all__ = [
    "detect_terminal_id",
    "detect_terminal_id_with_source",
    "normalize_terminal_id",
    "SOURCE_ENV",
    "SOURCE_CONSOLE",
    "SOURCE_FALLBACK",
    "TERMINAL_ENV_VARS",
]
