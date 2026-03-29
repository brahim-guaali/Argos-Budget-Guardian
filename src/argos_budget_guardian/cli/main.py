"""Argos Budget Guardian CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="argos",
    help="Argos Budget Guardian — Real-time cost tracking for the Claude Agent SDK",
    no_args_is_help=True,
)
console = Console()


@app.command()
def setup() -> None:
    """Interactive setup wizard — configure your default budget and preferences."""
    from argos_budget_guardian.cli.setup_wizard import run_wizard

    run_wizard()


@app.command()
def status() -> None:
    """Show current cost tracking status."""
    from argos_budget_guardian.core.store import Store

    try:
        store = Store()
    except Exception:
        console.print(
            "[yellow]No cost history found. Run an agent with GuardedAgent first.[/yellow]"
        )
        return

    today_total = store.get_today_total()
    sessions = store.get_sessions(limit=1)

    console.print()
    console.print("[bold]Argos Budget Guardian — Status[/bold]")
    console.print()
    console.print(f"  Today's spending: [bold green]${today_total:.4f}[/bold green]")

    if sessions:
        last = sessions[0]
        cost = last['total_cost_usd']
        events = last['num_events']
        console.print(f"  Last session:     ${cost:.4f} ({events} events)")
        console.print(f"  Started:          {last['started_at']}")
    else:
        console.print("  [dim]No sessions recorded yet.[/dim]")
    console.print()

    store.close()


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show"),
) -> None:
    """Show past session cost history."""
    from argos_budget_guardian.core.store import Store

    try:
        store = Store()
    except Exception:
        console.print("[yellow]No cost history found.[/yellow]")
        return

    sessions = store.get_sessions(limit=limit)

    if not sessions:
        console.print("[yellow]No sessions recorded yet.[/yellow]")
        store.close()
        return

    table = Table(title="Session History", show_header=True, header_style="bold cyan")
    table.add_column("Started", style="dim")
    table.add_column("Session ID", style="white", max_width=20)
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Events", justify="right")
    table.add_column("Status", style="dim")

    for s in sessions:
        status_str = "completed" if s["ended_at"] else "active"
        sid = s["session_id"][:18] + "..." if len(s["session_id"]) > 20 else s["session_id"]
        table.add_row(
            s["started_at"][:19],
            sid,
            f"${s['total_cost_usd']:.4f}",
            str(s["num_events"]),
            status_str,
        )

    console.print()
    console.print(table)

    # Summary
    total = sum(s["total_cost_usd"] for s in sessions)
    n = len(sessions)
    console.print(f"\n  Total across {n} sessions: [bold green]${total:.4f}[/bold green]\n")

    store.close()


@app.command()
def dashboard() -> None:
    """Launch live terminal dashboard."""
    from argos_budget_guardian.core.budget import BudgetPolicy
    from argos_budget_guardian.core.tracker import CostTracker
    from argos_budget_guardian.dashboard.terminal import run_dashboard

    config = _load_config()
    budget = config.get("budget", 10.0)
    policy = BudgetPolicy(max_cost_usd=budget)
    tracker = CostTracker()

    console.print("[dim]Starting dashboard... Press Ctrl+C to exit.[/dim]")
    run_dashboard(tracker, policy)


@app.command()
def config(
    show: bool = typer.Option(True, "--show", help="Show current configuration"),
) -> None:
    """View or edit configuration."""
    config_path = Path.home() / ".argos-budget-guardian" / "config.toml"

    if not config_path.exists():
        console.print("[yellow]No configuration found. Run 'argos setup' first.[/yellow]")
        return

    console.print(f"\n[bold]Configuration[/bold] ({config_path})\n")
    console.print(config_path.read_text())


@app.command()
def export(
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
    output: str = typer.Option(
        "argos_export", "--output", "-o", help="Output file path (without extension)"
    ),
) -> None:
    """Export cost history to CSV or JSON."""
    from argos_budget_guardian.core.store import Store

    store = Store()

    if format == "csv":
        out_path = f"{output}.csv"
        count = store.export_csv(out_path)
    elif format == "json":
        out_path = f"{output}.json"
        count = store.export_json(out_path)
    else:
        console.print(f"[red]Unknown format: {format}. Use 'csv' or 'json'.[/red]")
        store.close()
        return

    if count > 0:
        console.print(f"[green]Exported {count} events to {out_path}[/green]")
    else:
        console.print("[yellow]No events to export.[/yellow]")

    store.close()


@app.command()
def version() -> None:
    """Show version info."""
    from argos_budget_guardian import __version__

    console.print(f"Argos Budget Guardian v{__version__}")


def _load_config() -> dict:
    """Load config from TOML file if it exists."""
    config_path = Path.home() / ".argos-budget-guardian" / "config.toml"
    if not config_path.exists():
        return {}

    # Simple TOML parsing for basic key=value pairs
    config: dict = {}
    for line in config_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#") and not line.startswith("["):
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"')
            try:
                config[key] = float(value)
            except ValueError:
                config[key] = value
    return config


if __name__ == "__main__":
    app()
