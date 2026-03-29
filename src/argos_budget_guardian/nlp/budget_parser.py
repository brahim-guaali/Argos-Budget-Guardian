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

# Multi-word phrases are checked first via substring match; single words use
# word-boundary regex to avoid matching inside other words (e.g. "day" inside
# "yesterday").

# Scope keywords
_DAILY_PHRASES = {"per day", "a day", "/day"}
_DAILY_WORDS = {"day", "daily", "today"}
_GLOBAL_PHRASES = set[str]()
_GLOBAL_WORDS = {"total", "global", "ever", "lifetime", "overall"}

# Action keywords
_STOP_WORDS = {"stop", "halt", "block", "deny", "kill"}
_PAUSE_WORDS = {"pause", "wait", "slow", "cooldown"}
_WARN_WORDS = {"warn", "alert", "notify", "warning"}


def _has_keyword(text: str, phrases: set[str], words: set[str]) -> bool:
    """Check if *text* contains any of the given phrases or whole-words."""
    for phrase in phrases:
        if phrase in text:
            return True
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text):
            return True
    return False


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
    if _has_keyword(lower, _DAILY_PHRASES, _DAILY_WORDS):
        scope = "daily"
    elif _has_keyword(lower, _GLOBAL_PHRASES, _GLOBAL_WORDS):
        scope = "global"

    # Determine action
    action: Literal["warn", "pause", "stop"] = "stop"
    if _has_keyword(lower, set(), _WARN_WORDS):
        action = "warn"
    elif _has_keyword(lower, set(), _PAUSE_WORDS):
        action = "pause"
    elif _has_keyword(lower, set(), _STOP_WORDS):
        action = "stop"

    return BudgetPolicy(
        max_cost_usd=amount,
        scope=scope,
        action_on_limit=action,
    )
