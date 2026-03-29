"""Reusable Rich renderables for the terminal dashboard."""

from __future__ import annotations

from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from argos_budget_guardian.core.tracker import CostEvent, CostTracker


def budget_bar(current: float, maximum: float) -> Panel:
    """Render a color-coded budget utilization bar."""
    pct = min(current / maximum, 1.0) if maximum > 0 else 0.0
    pct_display = pct * 100

    if pct < 0.6:
        color = "green"
    elif pct < 0.8:
        color = "yellow"
    else:
        color = "red"

    bar = ProgressBar(total=100, completed=pct_display, style="bar.back", complete_style=color)

    label = Text.assemble(
        ("Budget: ", "bold"),
        (f"${current:.4f}", f"bold {color}"),
        (f" / ${maximum:.2f}", "dim"),
        (f"  ({pct_display:.1f}%)", color),
    )

    return Panel(
        Text.assemble(label, "\n", bar),
        title="Budget Utilization",
        border_style=color,
    )


def cost_ticker(total_cost: float) -> Panel:
    """Render a large cost ticker."""
    color = "green" if total_cost < 1.0 else "yellow" if total_cost < 5.0 else "red"
    cost_text = Text(f"${total_cost:.4f}", style=f"bold {color}")
    return Panel(cost_text, title="Current Cost", border_style="blue")


def model_breakdown_table(tracker: CostTracker, session_id: str | None = None) -> Table:
    """Render a table of costs broken down by model."""
    breakdown = tracker.get_breakdown(session_id)
    by_model = breakdown["by_model"]
    total = breakdown["total_cost_usd"]

    table = Table(title="Cost by Model", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="white")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("%", justify="right", style="dim")

    for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
        pct = (cost / total * 100) if total > 0 else 0
        # Shorten model name for display
        short_name = model.split("-202")[0] if "-202" in model else model
        table.add_row(short_name, f"${cost:.4f}", f"{pct:.1f}%")

    return table


def tool_call_log(events: list[CostEvent], max_rows: int = 10) -> Table:
    """Render a scrolling log of recent tool calls."""
    table = Table(title="Recent Activity", show_header=True, header_style="bold cyan")
    table.add_column("Time", style="dim", width=8)
    table.add_column("Type", style="white")
    table.add_column("Cost", justify="right", style="green")

    recent = events[-max_rows:]
    for event in reversed(recent):
        time_str = event.timestamp.strftime("%H:%M:%S")
        table.add_row(time_str, event.tool_name, f"${event.cost_usd:.4f}")

    return table


def token_summary(tracker: CostTracker, session_id: str | None = None) -> Text:
    """Render a token count summary."""
    breakdown = tracker.get_breakdown(session_id)
    return Text.assemble(
        ("Tokens: ", "bold"),
        (f"{breakdown['total_input_tokens']:,}", "cyan"),
        (" in / ", "dim"),
        (f"{breakdown['total_output_tokens']:,}", "cyan"),
        (" out / ", "dim"),
        (f"{breakdown['total_cache_read_tokens']:,}", "cyan"),
        (" cached", "dim"),
        ("  |  ", "dim"),
        ("Events: ", "bold"),
        (f"{breakdown['event_count']}", "cyan"),
    )


def status_header(session_active: bool = True) -> Text:
    """Render the dashboard header with session status."""
    status = ("SESSION ACTIVE", "bold green") if session_active else ("IDLE", "dim")
    return Text.assemble(
        ("Argos Budget Guardian", "bold white"),
        ("  ", ""),
        status,
    )
