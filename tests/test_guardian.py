"""Integration tests for GuardedAgent wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.tracker import CostEvent, CostTracker
from argos_budget_guardian.wrapper.guardian import GuardedAgent

# Helper to patch ClaudeCodeOptions so GuardedAgent can be constructed without the SDK.
_OPTS_PATCH = "argos_budget_guardian.wrapper.guardian.ClaudeCodeOptions"


def _make_agent(**kwargs):  # type: ignore[no-untyped-def]
    """Create a GuardedAgent with ClaudeCodeOptions patched out."""
    with patch(_OPTS_PATCH) as mock_opts:
        mock_opts.side_effect = lambda **kw: MagicMock(**kw)
        return GuardedAgent(**kwargs)


# ---------------------------------------------------------------------------
# Hook merging
# ---------------------------------------------------------------------------


class TestGuardedAgentBuildOptions:
    """Test hook merging logic (does not require SDK client)."""

    def test_creates_guardian_hooks(self) -> None:
        agent = _make_agent(budget=5.0)
        opts = agent._options
        assert "PreToolUse" in opts.hooks
        assert "Stop" in opts.hooks
        assert "SubagentStop" in opts.hooks

    def test_merges_user_hooks(self) -> None:
        user_matcher = MagicMock()
        user_hooks = {
            "PreToolUse": [user_matcher],
            "CustomEvent": [user_matcher],
        }
        user_options = MagicMock()
        user_options.hooks = user_hooks
        for attr in (
            "model", "max_turns", "system_prompt", "permission_mode",
            "allowed_tools", "disallowed_tools", "mcp_servers", "cwd",
        ):
            setattr(user_options, attr, None)

        with patch(_OPTS_PATCH) as mock_opts:
            mock_opts.side_effect = lambda **kw: MagicMock(**kw)
            agent = GuardedAgent(budget=5.0, options=user_options)
            merged = agent._options.hooks

        # Guardian PreToolUse hook + user PreToolUse hook
        assert len(merged["PreToolUse"]) == 2
        # User custom event preserved
        assert "CustomEvent" in merged
        assert merged["CustomEvent"] == [user_matcher]

    def test_parses_string_budget(self) -> None:
        agent = _make_agent(budget="$5 per day")
        assert agent._policy.max_cost_usd == 5.0
        assert agent._policy.scope == "daily"

    def test_accepts_policy_object(self) -> None:
        policy = BudgetPolicy(max_cost_usd=20.0, warn_at_percent=90.0)
        agent = _make_agent(budget=policy)
        assert agent._policy is policy


# ---------------------------------------------------------------------------
# Properties & cost report
# ---------------------------------------------------------------------------


class TestGuardedAgentProperties:
    """Test cost reporting properties."""

    def test_total_cost(self) -> None:
        agent = _make_agent(budget=10.0)
        agent._tracker.record(
            CostEvent.create(
                model="claude-sonnet-4-6",
                tool_name="test",
                cost_usd=2.50,
                session_id="s1",
            )
        )
        assert agent.total_cost == 2.50
        assert agent.budget_remaining == 7.50
        assert agent.utilization_percent == 25.0

    def test_cost_report_format(self) -> None:
        agent = _make_agent(budget=10.0)
        report = agent.cost_report()
        assert "Argos Budget Guardian" in report
        assert "Total Cost" in report
        assert "Budget" in report
        assert "$10.00" in report

    def test_session_id_generated(self) -> None:
        agent = _make_agent(budget=5.0)
        assert agent.session_id  # Non-empty UUID


# ---------------------------------------------------------------------------
# Cost tracking simulation (what query() does internally)
# ---------------------------------------------------------------------------


class TestGuardedAgentCostTracking:
    """Test cost tracking and reconciliation logic."""

    @pytest.mark.asyncio
    async def test_tracks_cost_and_reconciles(self) -> None:
        """Simulate what query() does: estimate cost, then reconcile."""
        from argos_budget_guardian.core.pricing import default_registry

        agent = _make_agent(budget=5.0)

        # Estimate cost the same way query() does
        cost = default_registry.estimate_cost(
            model="claude-sonnet-4-6-20250514",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost > 0

        agent._tracker.record(
            CostEvent.create(
                model="claude-sonnet-4-6-20250514",
                tool_name="api_call",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=cost,
                session_id="sess-1",
            )
        )
        assert agent._tracker.get_session_total("sess-1") == pytest.approx(cost)

        # Reconcile to authoritative cost
        agent._tracker.reconcile("sess-1", 0.0105)
        assert agent._tracker.get_session_total("sess-1") == 0.0105

    @pytest.mark.asyncio
    async def test_reconcile_adjusts_global_total(self) -> None:
        agent = _make_agent(budget=5.0)
        agent._tracker.record(
            CostEvent.create(
                model="claude-sonnet-4-6",
                tool_name="api_call",
                cost_usd=0.05,
                session_id="s1",
            )
        )
        assert agent.total_cost == pytest.approx(0.05)

        agent._tracker.reconcile("s1", 0.03)
        assert agent.total_cost == pytest.approx(0.03)
        assert agent.budget_remaining == pytest.approx(4.97)


# ---------------------------------------------------------------------------
# Budget scope integration (hook + tracker working together)
# ---------------------------------------------------------------------------


class TestBudgetHookScopeIntegration:
    """Test that budget hook respects policy scope."""

    @pytest.mark.asyncio
    async def test_session_scope_checks_session_total(self) -> None:
        from argos_budget_guardian.hooks.budget_hook import make_budget_hook

        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=1.0, scope="session")
        hook = make_budget_hook(tracker=tracker, policy=policy)

        # Record cost in session-1 (under budget)
        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.5, session_id="s1")
        )
        # Record cost in session-2 that pushes global over 1.0
        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.6, session_id="s2")
        )

        # Session-1 is under budget (0.5 < 1.0), should be allowed
        result = await hook(
            {"hook_event_name": "PreToolUse", "session_id": "s1"}, "tid", None
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_daily_scope_checks_global_total(self) -> None:
        from argos_budget_guardian.hooks.budget_hook import make_budget_hook

        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=1.0, scope="daily")
        hook = make_budget_hook(tracker=tracker, policy=policy)

        # Each session under 1.0, but combined >= 1.0
        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.6, session_id="s1")
        )
        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.5, session_id="s2")
        )

        # Daily scope checks global total (1.1 >= 1.0) — should block
        result = await hook(
            {"hook_event_name": "PreToolUse", "session_id": "s1"}, "tid", None
        )
        assert result["decision"] == "block"
        assert "Budget limit reached" in result["systemMessage"]

    @pytest.mark.asyncio
    async def test_global_scope_checks_global_total(self) -> None:
        from argos_budget_guardian.hooks.budget_hook import make_budget_hook

        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=1.0, scope="global")
        hook = make_budget_hook(tracker=tracker, policy=policy)

        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.6, session_id="s1")
        )
        tracker.record(
            CostEvent.create(model="m", tool_name="t", cost_usd=0.5, session_id="s2")
        )

        result = await hook(
            {"hook_event_name": "PreToolUse", "session_id": "s1"}, "tid", None
        )
        assert result["decision"] == "block"
        assert "Budget limit reached" in result["systemMessage"]

    @pytest.mark.asyncio
    async def test_daily_scope_with_store_callable(self) -> None:
        from argos_budget_guardian.hooks.budget_hook import make_budget_hook

        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=5.0, scope="daily")
        # Simulate store returning high daily total
        hook = make_budget_hook(
            tracker=tracker, policy=policy, get_daily_total=lambda: 5.5
        )

        result = await hook(
            {"hook_event_name": "PreToolUse", "session_id": "s1"}, "tid", None
        )
        assert result["decision"] == "block"
