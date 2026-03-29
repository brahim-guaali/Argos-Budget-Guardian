"""GuardedAgent — drop-in wrapper for claude_code_sdk.query() with budget enforcement."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Callable

from claude_code_sdk import (
    ClaudeCodeOptions,
    HookMatcher,
    ResultMessage,
)
from claude_code_sdk import (
    query as sdk_query,
)

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.pricing import PricingRegistry, default_registry
from argos_budget_guardian.core.store import Store
from argos_budget_guardian.core.tracker import CostEvent, CostTracker
from argos_budget_guardian.hooks.budget_hook import BudgetHook, make_budget_hook
from argos_budget_guardian.hooks.stop_hook import make_stop_hook
from argos_budget_guardian.nlp.budget_parser import parse_budget


class GuardedAgent:
    """Drop-in wrapper around claude_code_sdk.query() with real-time cost tracking
    and budget enforcement.

    Usage:
        async with GuardedAgent(budget=5.0) as agent:
            async for msg in agent.query("Analyze this code"):
                pass
            print(agent.cost_report())
    """

    def __init__(
        self,
        budget: float | str | BudgetPolicy = 10.0,
        options: ClaudeCodeOptions | None = None,
        on_warning: Callable[[float, float], Any] | None = None,
        on_limit: Callable[[float, float], Any] | None = None,
        dashboard: bool = False,
        pricing: PricingRegistry | None = None,
        store: Store | None = None,
    ) -> None:
        # Parse budget
        if isinstance(budget, (int, float)):
            self._policy = BudgetPolicy(max_cost_usd=float(budget))
        elif isinstance(budget, str):
            self._policy = parse_budget(budget)
        else:
            self._policy = budget

        self._tracker = CostTracker()
        self._pricing = pricing or default_registry
        self._on_warning = on_warning
        self._on_limit = on_limit
        self._dashboard = dashboard
        self._dashboard_thread: Any = None
        self._store = store
        self._session_id: str = str(uuid.uuid4())

        # Build options with merged hooks — keep reference to budget hook for reset
        self._budget_hook: BudgetHook | None = None
        self._options = self._build_options(options)

    def _build_options(self, user_options: ClaudeCodeOptions | None) -> ClaudeCodeOptions:
        """Build ClaudeCodeOptions with guardian hooks merged in."""
        # Create guardian hooks
        get_daily_total: Callable[[], float] | None = None
        if self._policy.scope in ("daily", "global") and self._store is not None:
            # Store holds costs from *previous* sessions; tracker holds the
            # current session.  Summing them avoids double-counting because
            # save_event() is only called at the end of a query (ResultMessage),
            # and the store won't include the current session's in-flight cost.
            get_daily_total = lambda: (  # noqa: E731
                self._store.get_today_total() + self._tracker.get_global_total()
            )

        budget_hook = make_budget_hook(
            tracker=self._tracker,
            policy=self._policy,
            on_warning=self._on_warning,
            on_limit=self._on_limit,
            get_daily_total=get_daily_total,
        )
        self._budget_hook = budget_hook
        stop_hook = make_stop_hook(tracker=self._tracker)

        guardian_hooks: dict[str, list[HookMatcher]] = {
            "PreToolUse": [HookMatcher(hooks=[budget_hook])],
            "Stop": [HookMatcher(hooks=[stop_hook])],
            "SubagentStop": [HookMatcher(hooks=[stop_hook])],
        }

        if user_options is None:
            return ClaudeCodeOptions(hooks=guardian_hooks)

        # Merge hooks: guardian hooks run first
        merged_hooks = dict(guardian_hooks)
        if user_options.hooks:
            for event, matchers in user_options.hooks.items():
                if event in merged_hooks:
                    merged_hooks[event] = merged_hooks[event] + matchers
                else:
                    merged_hooks[event] = matchers

        # Copy all user options, overriding only hooks.
        # Build kwargs from known fields to avoid dropping new SDK options.
        opts_kwargs: dict[str, Any] = {}
        for attr in (
            "model", "max_turns", "system_prompt", "permission_mode",
            "allowed_tools", "disallowed_tools", "mcp_servers", "cwd",
        ):
            value = getattr(user_options, attr, None)
            if value is not None:
                opts_kwargs[attr] = value
        opts_kwargs["hooks"] = merged_hooks

        return ClaudeCodeOptions(**opts_kwargs)

    async def query(self, prompt: str, **kwargs: Any) -> AsyncIterator[Any]:
        """Run a query with cost tracking and budget enforcement.

        Intercepts the message stream to track costs in real time.
        Yields all messages through to the caller.
        """
        # Re-arm warning/limit notifications for this query cycle
        if self._budget_hook is not None:
            self._budget_hook.reset()

        async for message in sdk_query(prompt=prompt, options=self._options, **kwargs):
            # Track costs from ResultMessage (authoritative)
            if isinstance(message, ResultMessage):
                if message.session_id:
                    self._session_id = message.session_id

                usage = message.usage or {}
                model = getattr(message, "model", None) or "unknown"

                # Record a cost event from the result's usage data
                if message.total_cost_usd is not None:
                    # Compute the incremental cost for this query by
                    # subtracting what the tracker already knows about
                    # this session (from prior queries).
                    previous = self._tracker.get_session_total(self._session_id)
                    incremental = max(0.0, message.total_cost_usd - previous)

                    event = CostEvent.create(
                        model=model,
                        tool_name="query",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                        cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                        cost_usd=incremental,
                        session_id=self._session_id,
                    )
                    self._tracker.record(event)
                    # Reconcile to the SDK's authoritative total in case
                    # of rounding differences.
                    self._tracker.reconcile(
                        self._session_id, message.total_cost_usd
                    )

                    # Persist to store if configured
                    if self._store is not None:
                        self._store.save_event(event)

            yield message

    def _get_scope_cost(self) -> float:
        """Get the current cost according to the policy scope."""
        if self._policy.scope == "session":
            return self._tracker.get_session_total(self._session_id)
        elif self._policy.scope == "daily":
            if self._store is not None:
                return self._store.get_today_total() + self._tracker.get_global_total()
            return self._tracker.get_global_total()
        else:  # global
            return self._tracker.get_global_total()

    @property
    def total_cost(self) -> float:
        """Total cost spent across all queries in this agent's lifetime."""
        return self._tracker.get_global_total()

    @property
    def budget_remaining(self) -> float:
        """Remaining budget in USD (scope-aware)."""
        return max(0.0, self._policy.max_cost_usd - self._get_scope_cost())

    @property
    def utilization_percent(self) -> float:
        """Budget utilization as a percentage (scope-aware)."""
        return self._policy.utilization_percent(self._get_scope_cost())

    @property
    def tracker(self) -> CostTracker:
        """Access the underlying cost tracker."""
        return self._tracker

    @property
    def policy(self) -> BudgetPolicy:
        """Access the budget policy."""
        return self._policy

    @property
    def session_id(self) -> str:
        """Current session ID."""
        return self._session_id

    def cost_report(self) -> str:
        """Generate a human-readable cost report."""
        breakdown = self._tracker.get_breakdown()
        total = breakdown["total_cost_usd"]
        lines = [
            "",
            "=== Argos Budget Guardian — Cost Report ===",
            "",
            f"  Total Cost:      ${total:.4f}",
            f"  Budget:          ${self._policy.max_cost_usd:.2f} ({self._policy.scope})",
            f"  Remaining:       ${self.budget_remaining:.4f}",
            f"  Utilization:     {self.utilization_percent:.1f}%",
            "",
        ]

        if breakdown["by_model"]:
            lines.append("  Cost by Model:")
            for model, cost in sorted(
                breakdown["by_model"].items(), key=lambda x: x[1], reverse=True
            ):
                pct = (cost / total * 100) if total > 0 else 0
                lines.append(f"    {model}: ${cost:.4f} ({pct:.1f}%)")
            lines.append("")

        lines.extend([
            f"  Tokens: {breakdown['total_input_tokens']:,} in"
            f" / {breakdown['total_output_tokens']:,} out"
            f" / {breakdown['total_cache_read_tokens']:,} cached",
            f"  API Calls: {breakdown['event_count']}",
            "",
            "============================================",
        ])

        return "\n".join(lines)

    async def __aenter__(self) -> GuardedAgent:
        if self._dashboard:
            import threading

            from argos_budget_guardian.dashboard.terminal import run_dashboard

            self._dashboard_thread = threading.Thread(
                target=run_dashboard,
                args=(self._tracker, self._policy),
                kwargs={"session_id": self._session_id},
                daemon=True,
            )
            self._dashboard_thread.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        # Finalize store session if configured
        if self._store is not None:
            self._store.finalize_session(self._session_id, self.total_cost)
