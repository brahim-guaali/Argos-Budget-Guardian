"""PreToolUse hook for budget enforcement."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine


from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.tracker import CostTracker

HookCallback = Callable[
    [dict[str, Any], str | None, Any],
    Coroutine[Any, Any, dict[str, Any]],
]


def make_budget_hook(
    tracker: CostTracker,
    policy: BudgetPolicy,
    on_warning: Callable[[float, float], Any] | None = None,
    on_limit: Callable[[float, float], Any] | None = None,
    get_daily_total: Callable[[], float] | None = None,
) -> HookCallback:
    """Create a PreToolUse hook that enforces budget limits.

    Args:
        tracker: The cost tracker to read current spending from.
        policy: The budget policy to enforce.
        on_warning: Optional callback when warning threshold is reached.
        on_limit: Optional callback when budget limit is reached.
        get_daily_total: Optional callable returning today's spending (for daily scope).

    Returns:
        An async hook function compatible with Claude Agent SDK.
    """
    _warning_emitted = False

    async def budget_check_hook(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        nonlocal _warning_emitted

        if input_data.get("hook_event_name") != "PreToolUse":
            return {}

        session_id = input_data.get("session_id", "")
        if policy.scope == "session":
            current_cost = tracker.get_session_total(session_id)
        elif policy.scope == "daily":
            if get_daily_total is not None:
                current_cost = get_daily_total()
            else:
                current_cost = tracker.get_global_total()
        else:  # global
            current_cost = tracker.get_global_total()

        # Check if over budget
        if policy.is_over_budget(current_cost):
            if on_limit:
                on_limit(current_cost, policy.max_cost_usd)

            reason = (
                f"[Argos] Budget limit reached: "
                f"${current_cost:.4f} / ${policy.max_cost_usd:.2f} "
                f"({policy.utilization_percent(current_cost):.0f}%)"
            )

            if policy.action_on_limit == "stop":
                return {
                    "decision": "block",
                    "systemMessage": reason,
                }
            elif policy.action_on_limit == "pause":
                if policy.cooldown_seconds > 0:
                    await asyncio.sleep(policy.cooldown_seconds)
                return {
                    "systemMessage": (
                        f"[Argos] Budget limit reached: "
                        f"${current_cost:.4f} / ${policy.max_cost_usd:.2f}. "
                        f"Resuming after {policy.cooldown_seconds}s cooldown."
                    )
                }
            else:  # warn
                return {
                    "systemMessage": (
                        f"[Argos] WARNING: Budget exceeded: "
                        f"${current_cost:.4f} / ${policy.max_cost_usd:.2f}"
                    )
                }

        # Check if at warning threshold
        if policy.is_at_warning(current_cost) and not _warning_emitted:
            _warning_emitted = True
            if on_warning:
                on_warning(current_cost, policy.max_cost_usd)
            return {
                "systemMessage": (
                    f"[Argos] Budget warning: "
                    f"${current_cost:.4f} / ${policy.max_cost_usd:.2f} "
                    f"({policy.utilization_percent(current_cost):.0f}% used)"
                )
            }

        return {}

    return budget_check_hook
