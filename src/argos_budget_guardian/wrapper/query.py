"""Functional wrapper — drop-in replacement for claude_code_sdk.query()."""

from __future__ import annotations

from typing import Any, AsyncIterator

from claude_code_sdk import ClaudeCodeOptions

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.wrapper.guardian import GuardedAgent


async def guarded_query(
    prompt: str,
    budget: float | str | BudgetPolicy = 10.0,
    options: ClaudeCodeOptions | None = None,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Run a single query with budget enforcement.

    Drop-in replacement for claude_code_sdk.query() that adds cost tracking.

    Usage:
        async for msg in guarded_query("Analyze this code", budget=5.0):
            print(msg)

    Args:
        prompt: The prompt to send to the agent.
        budget: Budget limit — dollar amount, natural language string, or BudgetPolicy.
        options: Optional ClaudeCodeOptions (hooks will be merged).
        **kwargs: Additional keyword arguments passed to the agent query.

    Yields:
        Messages from the agent, same as claude_code_sdk.query().
    """
    agent = GuardedAgent(budget=budget, options=options)
    async with agent:
        async for message in agent.query(prompt, **kwargs):
            yield message
