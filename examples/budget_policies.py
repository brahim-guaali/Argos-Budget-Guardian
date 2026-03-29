"""Examples of different budget policy configurations."""

import asyncio

from argos_budget_guardian import BudgetPolicy, GuardedAgent


async def session_budget():
    """Basic session budget — stops at $5."""
    async with GuardedAgent(budget=5.0) as agent:
        async for msg in agent.query("Analyze this codebase"):
            pass
        print(agent.cost_report())


async def daily_budget():
    """Daily budget — $10 per day, warns at 70%."""
    policy = BudgetPolicy(
        max_cost_usd=10.0,
        warn_at_percent=70,
        scope="daily",
    )
    async with GuardedAgent(budget=policy) as agent:
        async for msg in agent.query("Review all pull requests"):
            pass


async def natural_language_budget():
    """Natural language budget — parsed from a string."""
    async with GuardedAgent(budget="spend no more than $5 today") as agent:
        async for msg in agent.query("Write unit tests"):
            pass


async def pause_on_limit():
    """Pause instead of stopping when budget is reached."""
    policy = BudgetPolicy(
        max_cost_usd=3.0,
        action_on_limit="pause",
        cooldown_seconds=5,
    )
    async with GuardedAgent(budget=policy) as agent:
        async for msg in agent.query("Refactor the auth module"):
            pass


if __name__ == "__main__":
    asyncio.run(session_budget())
