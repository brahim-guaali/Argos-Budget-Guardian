"""Cost tracker — central in-memory accumulator for real-time cost tracking."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CostEvent:
    """A single cost event recorded during agent execution."""

    timestamp: datetime
    model: str
    tool_name: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float
    session_id: str
    agent_id: str | None = None

    @classmethod
    def create(
        cls,
        model: str,
        tool_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cost_usd: float = 0.0,
        session_id: str = "",
        agent_id: str | None = None,
    ) -> CostEvent:
        """Create a CostEvent with the current timestamp."""
        return cls(
            timestamp=datetime.now(timezone.utc),
            model=model,
            tool_name=tool_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cost_usd=cost_usd,
            session_id=session_id,
            agent_id=agent_id,
        )


UpdateCallback = Callable[[CostEvent], Any]


@dataclass
class CostTracker:
    """Thread-safe, observable cost accumulator.

    Tracks costs at three granularities: per-event, per-session, and global.
    Supports real-time callbacks for dashboard updates.
    """

    _events: list[CostEvent] = field(default_factory=list)
    _session_totals: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _global_total: float = 0.0
    _callbacks: list[UpdateCallback] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, event: CostEvent) -> None:
        """Record a cost event and notify subscribers."""
        with self._lock:
            self._events.append(event)
            self._session_totals[event.session_id] += event.cost_usd
            self._global_total += event.cost_usd

        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                logger.exception("Error in cost tracker callback")

    def get_session_total(self, session_id: str) -> float:
        """Get total cost for a specific session."""
        with self._lock:
            return self._session_totals.get(session_id, 0.0)

    def get_global_total(self) -> float:
        """Get total cost across all sessions."""
        with self._lock:
            return self._global_total

    def get_session_events(self, session_id: str) -> list[CostEvent]:
        """Get all events for a specific session."""
        with self._lock:
            return [e for e in self._events if e.session_id == session_id]

    def get_breakdown(self, session_id: str | None = None) -> dict[str, Any]:
        """Get cost breakdown by model and by tool.

        If session_id is provided, scopes to that session. Otherwise, global.
        """
        with self._lock:
            events = (
                [e for e in self._events if e.session_id == session_id]
                if session_id
                else list(self._events)
            )

        by_model: dict[str, float] = defaultdict(float)
        by_tool: dict[str, float] = defaultdict(float)
        total_input = 0
        total_output = 0
        total_cache_read = 0

        for event in events:
            by_model[event.model] += event.cost_usd
            by_tool[event.tool_name] += event.cost_usd
            total_input += event.input_tokens
            total_output += event.output_tokens
            total_cache_read += event.cache_read_tokens

        total_cost = sum(e.cost_usd for e in events)

        return {
            "total_cost_usd": total_cost,
            "by_model": dict(by_model),
            "by_tool": dict(by_tool),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_read_tokens": total_cache_read,
            "event_count": len(events),
        }

    def reconcile(self, session_id: str, actual_cost: float) -> None:
        """Reconcile estimated costs with the authoritative cost from ResultMessage.

        Adjusts the session total to match the SDK's reported total_cost_usd.
        """
        with self._lock:
            current = self._session_totals.get(session_id, 0.0)
            diff = actual_cost - current
            self._session_totals[session_id] = actual_cost
            self._global_total += diff

    def on_update(self, callback: UpdateCallback) -> None:
        """Register a callback to be notified on every cost event."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: UpdateCallback) -> None:
        """Remove a previously registered callback."""
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    @property
    def events(self) -> list[CostEvent]:
        """Get a copy of all recorded events."""
        with self._lock:
            return list(self._events)

    @property
    def session_ids(self) -> list[str]:
        """Get all known session IDs."""
        with self._lock:
            return list(self._session_totals.keys())

    def reset(self) -> None:
        """Clear all tracked data."""
        with self._lock:
            self._events.clear()
            self._session_totals.clear()
            self._global_total = 0.0
