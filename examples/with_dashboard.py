"""Example: Run agent with live terminal dashboard."""

import asyncio

from argos_budget_guardian import GuardedAgent


async def main():
    async with GuardedAgent(budget=10.0, dashboard=True) as agent:
        async for msg in agent.query("Analyze and improve the test suite"):
            pass  # Dashboard shows live costs in the terminal

        print(agent.cost_report())


if __name__ == "__main__":
    asyncio.run(main())
