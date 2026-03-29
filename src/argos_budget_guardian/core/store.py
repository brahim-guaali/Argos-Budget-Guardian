"""SQLite persistent storage for cost history."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from argos_budget_guardian.core.tracker import CostEvent

DEFAULT_DB_PATH = Path.home() / ".argos-budget-guardian" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    total_cost_usd REAL NOT NULL DEFAULT 0,
    num_events INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cost_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    model TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_creation_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    session_id TEXT NOT NULL,
    agent_id TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS daily_totals (
    date TEXT PRIMARY KEY,
    total_cost_usd REAL NOT NULL DEFAULT 0,
    num_sessions INTEGER NOT NULL DEFAULT 0,
    num_events INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_session ON cost_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON cost_events(timestamp);
"""


class Store:
    """Lightweight SQLite store for persisting cost history.

    Stores sessions, individual cost events, and daily aggregates.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def save_event(self, event: CostEvent) -> None:
        """Save a single cost event."""
        # Ensure session exists
        self._conn.execute(
            """INSERT INTO sessions (session_id, started_at, total_cost_usd, num_events)
               VALUES (?, ?, 0, 0)
               ON CONFLICT(session_id) DO NOTHING""",
            (event.session_id, event.timestamp.isoformat()),
        )

        # Insert event
        self._conn.execute(
            """INSERT INTO cost_events
               (timestamp, model, tool_name, input_tokens, output_tokens,
                cache_read_tokens, cache_creation_tokens, cost_usd, session_id, agent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.timestamp.isoformat(),
                event.model,
                event.tool_name,
                event.input_tokens,
                event.output_tokens,
                event.cache_read_tokens,
                event.cache_creation_tokens,
                event.cost_usd,
                event.session_id,
                event.agent_id,
            ),
        )

        # Update session totals
        self._conn.execute(
            """UPDATE sessions
               SET total_cost_usd = total_cost_usd + ?,
                   num_events = num_events + 1
               WHERE session_id = ?""",
            (event.cost_usd, event.session_id),
        )

        # Update daily totals
        today = event.timestamp.strftime("%Y-%m-%d")
        self._conn.execute(
            """INSERT INTO daily_totals (date, total_cost_usd, num_sessions, num_events)
               VALUES (?, ?, 0, 1)
               ON CONFLICT(date) DO UPDATE SET
                   total_cost_usd = total_cost_usd + ?,
                   num_events = num_events + 1""",
            (today, event.cost_usd, event.cost_usd),
        )

        self._conn.commit()

    def finalize_session(self, session_id: str, total_cost: float) -> None:
        """Mark a session as ended and set its final cost."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """UPDATE sessions
               SET ended_at = ?, total_cost_usd = ?
               WHERE session_id = ?""",
            (now, total_cost, session_id),
        )
        self._conn.commit()

    def get_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent sessions ordered by start time."""
        rows = self._conn.execute(
            """SELECT session_id, started_at, ended_at, total_cost_usd, num_events
               FROM sessions ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_daily_totals(self, days: int = 30) -> list[dict[str, Any]]:
        """Get daily cost totals for the last N days."""
        rows = self._conn.execute(
            """SELECT date, total_cost_usd, num_sessions, num_events
               FROM daily_totals ORDER BY date DESC LIMIT ?""",
            (days,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_today_total(self) -> float:
        """Get total cost for today."""
        today = date.today().isoformat()
        row = self._conn.execute(
            "SELECT total_cost_usd FROM daily_totals WHERE date = ?",
            (today,),
        ).fetchone()
        return row["total_cost_usd"] if row else 0.0

    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific session."""
        rows = self._conn.execute(
            """SELECT * FROM cost_events
               WHERE session_id = ? ORDER BY timestamp""",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def export_csv(self, output_path: Path | str) -> int:
        """Export all cost events to CSV. Returns number of rows exported."""
        import csv

        rows = self._conn.execute(
            "SELECT * FROM cost_events ORDER BY timestamp"
        ).fetchall()

        if not rows:
            return 0

        output_path = Path(output_path)
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

        return len(rows)

    def export_json(self, output_path: Path | str) -> int:
        """Export all cost events to JSON. Returns number of rows exported."""
        import json

        rows = self._conn.execute(
            "SELECT * FROM cost_events ORDER BY timestamp"
        ).fetchall()

        output_path = Path(output_path)
        data = [dict(row) for row in rows]
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return len(data)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
