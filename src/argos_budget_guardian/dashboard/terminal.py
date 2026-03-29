"""Rich-based live terminal dashboard."""

from __future__ import annotations

import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.tracker import CostTracker
from argos_budget_guardian.dashboard.components import (
    budget_bar,
    cost_ticker,
    model_breakdown_table,
    status_header,
    token_summary,
    tool_call_log,
)


def _build_layout(
    tracker: CostTracker,
    policy: BudgetPolicy,
    session_id: str | None = None,
) -> Layout:
    """Build the dashboard layout."""
    layout = Layout()

    total = tracker.get_global_total()
    events = tracker.events

    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="cost", size=5),
        Layout(name="budget", size=5),
        Layout(name="middle", size=12),
        Layout(name="footer", size=3),
    )

    layout["header"].update(status_header(session_active=len(events) > 0))
    layout["cost"].update(cost_ticker(total))
    layout["budget"].update(budget_bar(total, policy.max_cost_usd))

    layout["middle"].split_row(
        Layout(name="models"),
        Layout(name="log"),
    )
    layout["models"].update(Panel(model_breakdown_table(tracker, session_id)))
    layout["log"].update(Panel(tool_call_log(events)))

    layout["footer"].update(Panel(token_summary(tracker, session_id)))

    return layout


def run_dashboard(
    tracker: CostTracker,
    policy: BudgetPolicy,
    session_id: str | None = None,
    refresh_rate: float = 0.5,
) -> None:
    """Run the live terminal dashboard.

    This blocks and refreshes the display at the given rate.
    Press Ctrl+C to exit.

    Args:
        tracker: Cost tracker to read data from.
        policy: Budget policy for utilization display.
        session_id: Optional session to focus on.
        refresh_rate: Seconds between refreshes.
    """
    console = Console()

    try:
        with Live(
            _build_layout(tracker, policy, session_id),
            console=console,
            refresh_per_second=int(1 / refresh_rate),
            screen=True,
        ) as live:
            while True:
                time.sleep(refresh_rate)
                live.update(_build_layout(tracker, policy, session_id))
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard closed.[/dim]")
