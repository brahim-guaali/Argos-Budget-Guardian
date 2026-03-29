"""PreToolUse hook for budget enforcement."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.tracker import CostTracker


class BudgetHook:
    """Stateful budget enforcement hook for the Claude Agent SDK.

    Tracks whether warning/limit notifications have been emitted to avoid
    duplicate alerts within a single query cycle. Call ``reset()`` between
    queries to re-arm notifications.
    """

    def __init__(
        self,
        tracker: CostTracker,
        policy: BudgetPolicy,
        on_warning: Callable[[float, float], Any] | None = None,
        on_limit: Callable[[float, float], Any] | None = None,
        get_daily_total: Callable[[], float] | None = None,
    ) -> None:
        self._tracker = tracker
        self._policy = policy
        self._on_warning = on_warning
        self._on_limit = on_limit
        self._get_daily_total = get_daily_total
        self._warning_emitted = False
        self._limit_emitted = False

    def reset(self) -> None:
        """Re-arm warning and limit notifications for a new query cycle."""
        self._warning_emitted = False
        self._limit_emitted = False

    async def __call__(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        context: Any,
    ) -> dict[str, Any]:
        if input_data.get("hook_event_name") != "PreToolUse":
            return {}

        current_cost = self._resolve_current_cost(
            input_data.get("session_id", ""),
        )

        # Check if over budget
        if self._policy.is_over_budget(current_cost):
            if self._on_limit and not self._limit_emitted:
                self._limit_emitted = True
                self._on_limit(current_cost, self._policy.max_cost_usd)

            reason = (
                f"[Argos] Budget limit reached: "
                f"${current_cost:.4f} / ${self._policy.max_cost_usd:.2f} "
                f"({self._policy.utilization_percent(current_cost):.0f}%)"
            )

            if self._policy.action_on_limit == "stop":
                return {
                    "decision": "block",
                    "systemMessage": reason,
                }
            elif self._policy.action_on_limit == "pause":
                if self._policy.cooldown_seconds > 0:
                    await asyncio.sleep(self._policy.cooldown_seconds)
                return {
                    "systemMessage": (
                        f"[Argos] Budget limit reached: "
                        f"${current_cost:.4f} / ${self._policy.max_cost_usd:.2f}. "
                        f"Resuming after {self._policy.cooldown_seconds}s cooldown."
                    )
                }
            else:  # warn
                return {
                    "systemMessage": (
                        f"[Argos] WARNING: Budget exceeded: "
                        f"${current_cost:.4f} / ${self._policy.max_cost_usd:.2f}"
                    )
                }

        # Check if at warning threshold
        if self._policy.is_at_warning(current_cost) and not self._warning_emitted:
            self._warning_emitted = True
            if self._on_warning:
                self._on_warning(current_cost, self._policy.max_cost_usd)
            return {
                "systemMessage": (
                    f"[Argos] Budget warning: "
                    f"${current_cost:.4f} / ${self._policy.max_cost_usd:.2f} "
                    f"({self._policy.utilization_percent(current_cost):.0f}% used)"
                )
            }

        return {}

    def _resolve_current_cost(self, session_id: str) -> float:
        """Resolve the current cost based on the policy scope."""
        if self._policy.scope == "session":
            return self._tracker.get_session_total(session_id)
        elif self._policy.scope == "daily":
            if self._get_daily_total is not None:
                return self._get_daily_total()
            return self._tracker.get_global_total()
        else:  # global
            return self._tracker.get_global_total()


def make_budget_hook(
    tracker: CostTracker,
    policy: BudgetPolicy,
    on_warning: Callable[[float, float], Any] | None = None,
    on_limit: Callable[[float, float], Any] | None = None,
    get_daily_total: Callable[[], float] | None = None,
) -> BudgetHook:
    """Create a PreToolUse hook that enforces budget limits.

    Args:
        tracker: The cost tracker to read current spending from.
        policy: The budget policy to enforce.
        on_warning: Optional callback when warning threshold is reached.
        on_limit: Optional callback when budget limit is reached.
        get_daily_total: Optional callable returning today's spending (for daily scope).

    Returns:
        A BudgetHook instance callable compatible with Claude Agent SDK.
    """
    return BudgetHook(
        tracker=tracker,
        policy=policy,
        on_warning=on_warning,
        on_limit=on_limit,
        get_daily_total=get_daily_total,
    )
