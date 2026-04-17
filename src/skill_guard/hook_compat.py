"""Compatibility helpers for skill-guard hook entrypoints."""

from __future__ import annotations

from typing import Any, Callable

try:
    from UserPromptSubmit_modules.base import HookResult as _HookResult
    from UserPromptSubmit_modules.registry import register_hook as _register_hook
except Exception:  # pragma: no cover - package must import outside hook runtime

    class _HookResult:
        def __init__(
            self,
            context: Any = None,
            tokens: int = 0,
            priority: float = 10.0,
            tokens_added: int | None = None,
        ) -> None:
            self.context = context
            self.tokens = tokens_added if tokens_added is not None else tokens
            self.priority = priority

        def is_empty(self) -> bool:
            return not self.context

        @classmethod
        def empty(cls) -> _HookResult:
            return cls(context=None, tokens=0)

    def _register_hook(name: str, priority: float = 10.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator


HookResult = _HookResult
register_hook = _register_hook

__all__ = ["HookResult", "register_hook"]
