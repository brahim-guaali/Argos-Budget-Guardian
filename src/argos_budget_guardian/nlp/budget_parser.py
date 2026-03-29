"""Natural language budget parser.

Parses human-friendly budget strings into BudgetPolicy objects.
Uses simple regex patterns — no ML required.
"""

from __future__ import annotations

import re
from typing import Literal

from argos_budget_guardian.core.budget import BudgetPolicy

# Pattern: dollar amount like "$5", "$10.50", "5.00"
_AMOUNT_PATTERN = re.compile(r"\$?\s*(\d+(?:\.\d+)?)")

# Scope keywords
_DAILY_KEYWORDS = {"day", "daily", "today", "per day", "a day", "/day"}
_GLOBAL_KEYWORDS = {"total", "global", "ever", "lifetime", "overall"}

# Action keywords
_STOP_KEYWORDS = {"stop", "halt", "block", "deny", "kill"}
_PAUSE_KEYWORDS = {"pause", "wait", "slow", "cooldown"}
_WARN_KEYWORDS = {"warn", "alert", "notify", "warning"}


def parse_budget(text: str) -> BudgetPolicy:
    """Parse a natural language budget string into a BudgetPolicy.

    Examples:
        "$5"                          -> BudgetPolicy(max=5.0, scope="session")
        "$10 per day"                 -> BudgetPolicy(max=10.0, scope="daily")
        "spend no more than $5 today" -> BudgetPolicy(max=5.0, scope="daily")
        "$20 total"                   -> BudgetPolicy(max=20.0, scope="global")
        "$5 per day, warn only"       -> BudgetPolicy(max=5.0, scope="daily", action="warn")

    Args:
        text: Human-readable budget string.

    Returns:
        A BudgetPolicy parsed from the text.

    Raises:
        ValueError: If no dollar amount can be found in the text.
    """
    lower = text.lower().strip()

    # Extract dollar amount
    match = _AMOUNT_PATTERN.search(lower)
    if not match:
        raise ValueError(
            f"Could not find a dollar amount in: '{text}'. "
            "Try something like '$5', '$10 per day', or 'spend no more than $5 today'."
        )
    amount = float(match.group(1))

    # Determine scope
    scope: Literal["session", "daily", "global"] = "session"
    if any(kw in lower for kw in _DAILY_KEYWORDS):
        scope = "daily"
    elif any(kw in lower for kw in _GLOBAL_KEYWORDS):
        scope = "global"

    # Determine action
    action: Literal["warn", "pause", "stop"] = "stop"
    if any(kw in lower for kw in _WARN_KEYWORDS):
        action = "warn"
    elif any(kw in lower for kw in _PAUSE_KEYWORDS):
        action = "pause"
    elif any(kw in lower for kw in _STOP_KEYWORDS):
        action = "stop"

    return BudgetPolicy(
        max_cost_usd=amount,
        scope=scope,
        action_on_limit=action,
    )
