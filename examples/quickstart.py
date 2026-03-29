"""Quickstart — 5-line example of Argos Budget Guardian."""

import asyncio

from argos_budget_guardian import guarded_query


async def main():
    async for msg in guarded_query("What is 2 + 2?", budget=1.0):
        print(msg)


if __name__ == "__main__":
    asyncio.run(main())
