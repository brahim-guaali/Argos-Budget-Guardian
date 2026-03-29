"""Budget policy configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class BudgetPolicy:
    """Declarative budget configuration for agent cost control.

    Args:
        max_cost_usd: Hard spending ceiling in USD.
        warn_at_percent: Emit a warning when this percentage of the budget is used.
        action_on_limit: What happens when the budget is exceeded.
            - "stop": Deny further tool calls (default).
            - "pause": Pause execution for cooldown_seconds, then continue.
            - "warn": Allow execution but emit a warning.
        scope: Budget time scope.
            - "session": Resets per agent session (default).
            - "daily": Resets at midnight.
            - "global": Never resets.
        cooldown_seconds: How long to pause when action_on_limit is "pause".
    """

    max_cost_usd: float
    warn_at_percent: float = 80.0
    action_on_limit: Literal["warn", "pause", "stop"] = "stop"
    scope: Literal["session", "daily", "global"] = "session"
    cooldown_seconds: float = 0

    def __post_init__(self) -> None:
        if self.max_cost_usd <= 0:
            raise ValueError(f"max_cost_usd must be positive, got {self.max_cost_usd}")
        if not 0 < self.warn_at_percent <= 100:
            raise ValueError(f"warn_at_percent must be between 0 and 100, got {self.warn_at_percent}")
        if self.cooldown_seconds < 0:
            raise ValueError(f"cooldown_seconds must be non-negative, got {self.cooldown_seconds}")

    @property
    def warn_threshold_usd(self) -> float:
        """Dollar amount at which to emit a warning."""
        return self.max_cost_usd * (self.warn_at_percent / 100)

    def is_over_budget(self, current_cost: float) -> bool:
        """Check if the current cost exceeds the budget."""
        return current_cost >= self.max_cost_usd

    def is_at_warning(self, current_cost: float) -> bool:
        """Check if the current cost has reached the warning threshold."""
        return current_cost >= self.warn_threshold_usd and not self.is_over_budget(current_cost)

    def utilization_percent(self, current_cost: float) -> float:
        """Get budget utilization as a percentage."""
        return min((current_cost / self.max_cost_usd) * 100, 100.0)
