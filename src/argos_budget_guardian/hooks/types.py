"""Shared types for hook modules."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

HookCallback = Callable[
    [dict[str, Any], str | None, Any],
    Coroutine[Any, Any, dict[str, Any]],
]
