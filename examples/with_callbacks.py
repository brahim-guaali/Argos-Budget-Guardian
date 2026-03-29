"""Example: Budget callbacks for alerts and integrations."""

import asyncio

from argos_budget_guardian import GuardedAgent


def on_warning(current: float, limit: float):
    """Called when approaching budget threshold."""
    pct = current / limit * 100
    print(f"[WARNING] Budget at {pct:.0f}%: ${current:.4f} / ${limit:.2f}")


def on_limit(current: float, limit: float):
    """Called when budget limit is reached."""
    print(f"[LIMIT] Budget exhausted: ${current:.4f} / ${limit:.2f}")
    # You could send a Slack message, email, etc. here


async def main():
    async with GuardedAgent(
        budget=5.0,
        on_warning=on_warning,
        on_limit=on_limit,
    ) as agent:
        async for msg in agent.query("Fix all lint errors in the codebase"):
            pass

        print(agent.cost_report())


if __name__ == "__main__":
    asyncio.run(main())
