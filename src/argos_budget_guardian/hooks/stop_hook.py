"""Stop/SubagentStop hooks for session finalization."""

from __future__ import annotations

from typing import Any, Callable

from argos_budget_guardian.core.tracker import CostTracker
from argos_budget_guardian.hooks.types import HookCallback


def make_stop_hook(
    tracker: CostTracker,
    on_session_end: Callable[[str, float], Any] | None = None,
) -> HookCallback:
    """Create a Stop/SubagentStop hook for session finalization.

    Args:
        tracker: The cost tracker to read final costs from.
        on_session_end: Optional callback with (session_id, total_cost).

    Returns:
        An async hook function compatible with Claude Agent SDK.
    """

    async def stop_hook(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        event_name = input_data.get("hook_event_name", "")
        if event_name not in ("Stop", "SubagentStop"):
            return {}

        session_id = input_data.get("session_id", "")
        total_cost = tracker.get_session_total(session_id)

        if on_session_end:
            on_session_end(session_id, total_cost)

        return {}

    return stop_hook
