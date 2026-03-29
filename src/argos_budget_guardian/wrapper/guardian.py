"""GuardedAgent — drop-in wrapper for ClaudeSDKClient with budget enforcement."""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
)

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.pricing import PricingRegistry, default_registry
from argos_budget_guardian.core.tracker import CostEvent, CostTracker
from argos_budget_guardian.hooks.budget_hook import make_budget_hook
from argos_budget_guardian.hooks.stop_hook import make_stop_hook
from argos_budget_guardian.nlp.budget_parser import parse_budget


class GuardedAgent:
    """Drop-in wrapper around ClaudeSDKClient with real-time cost tracking and budget enforcement.

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
        self._client: ClaudeSDKClient | None = None
        self._current_session_id: str = ""

        # Build options with merged hooks
        self._options = self._build_options(options)

    def _build_options(self, user_options: ClaudeCodeOptions | None) -> ClaudeCodeOptions:
        """Build ClaudeCodeOptions with guardian hooks merged in."""
        # Create guardian hooks
        budget_hook = make_budget_hook(
            tracker=self._tracker,
            policy=self._policy,
            on_warning=self._on_warning,
            on_limit=self._on_limit,
        )
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

        # Create new options with merged hooks, preserving all other settings
        return ClaudeCodeOptions(
            model=user_options.model,
            max_turns=user_options.max_turns,
            system_prompt=user_options.system_prompt,
            permission_mode=user_options.permission_mode,
            allowed_tools=user_options.allowed_tools,
            disallowed_tools=user_options.disallowed_tools,
            mcp_servers=user_options.mcp_servers,
            cwd=user_options.cwd,
            hooks=merged_hooks,
        )

    async def query(self, prompt: str, **kwargs: Any) -> AsyncIterator[Any]:
        """Run a query with cost tracking and budget enforcement.

        Intercepts the message stream to track costs in real time.
        Yields all messages through to the caller.
        """
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options)
            await self._client.connect()

        await self._client.query(prompt, **kwargs)

        last_model = "unknown"

        async for message in self._client.receive_response():
            # Track costs from AssistantMessage usage
            if isinstance(message, AssistantMessage):
                last_model = getattr(message, "model", last_model)
                usage = getattr(message, "usage", None)
                if usage and isinstance(usage, dict):
                    cost = self._pricing.estimate_cost(
                        model=last_model,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                        cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                    )
                    if cost > 0:
                        self._tracker.record(
                            CostEvent.create(
                                model=last_model,
                                tool_name="api_call",
                                input_tokens=usage.get("input_tokens", 0),
                                output_tokens=usage.get("output_tokens", 0),
                                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                                cost_usd=cost,
                                session_id=self._current_session_id,
                            )
                        )

            # Reconcile with authoritative cost at session end
            if isinstance(message, ResultMessage):
                self._current_session_id = getattr(message, "session_id", "")
                actual_cost = getattr(message, "total_cost_usd", None)
                if actual_cost is not None and self._current_session_id:
                    self._tracker.reconcile(self._current_session_id, actual_cost)

            yield message

    @property
    def total_cost(self) -> float:
        """Total cost spent across all queries."""
        return self._tracker.get_global_total()

    @property
    def budget_remaining(self) -> float:
        """Remaining budget in USD."""
        return max(0.0, self._policy.max_cost_usd - self.total_cost)

    @property
    def utilization_percent(self) -> float:
        """Budget utilization as a percentage."""
        return self._policy.utilization_percent(self.total_cost)

    @property
    def tracker(self) -> CostTracker:
        """Access the underlying cost tracker."""
        return self._tracker

    @property
    def policy(self) -> BudgetPolicy:
        """Access the budget policy."""
        return self._policy

    def cost_report(self) -> str:
        """Generate a human-readable cost report."""
        breakdown = self._tracker.get_breakdown()
        total = breakdown["total_cost_usd"]
        lines = [
            "",
            "=== Argos Budget Guardian — Cost Report ===",
            "",
            f"  Total Cost:      ${total:.4f}",
            f"  Budget:          ${self._policy.max_cost_usd:.2f}",
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
        self._client = ClaudeSDKClient(options=self._options)
        await self._client.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
