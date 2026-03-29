"""Tests for budget enforcement and stop hooks."""

import pytest

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.tracker import CostEvent, CostTracker
from argos_budget_guardian.hooks.budget_hook import make_budget_hook
from argos_budget_guardian.hooks.stop_hook import make_stop_hook


@pytest.fixture
def tracker_with_cost():
    """Tracker with some pre-recorded cost."""
    tracker = CostTracker()
    tracker.record(
        CostEvent.create(model="s", tool_name="t", cost_usd=8.0, session_id="s1")
    )
    return tracker


def _make_input(session_id: str = "s1", tool_name: str = "Write") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": {},
        "tool_use_id": "tu1",
    }


class TestBudgetHook:
    @pytest.mark.asyncio
    async def test_allows_under_budget(self):
        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=10.0)
        hook = make_budget_hook(tracker, policy)
        result = await hook(_make_input(), "tu1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_denies_over_budget(self, tracker_with_cost):
        policy = BudgetPolicy(max_cost_usd=5.0, action_on_limit="stop")
        hook = make_budget_hook(tracker_with_cost, policy)
        result = await hook(_make_input(), "tu1", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Budget limit reached" in result["hookSpecificOutput"]["permissionDecisionReason"]

    @pytest.mark.asyncio
    async def test_warns_at_threshold(self):
        tracker = CostTracker()
        tracker.record(
            CostEvent.create(model="s", tool_name="t", cost_usd=8.5, session_id="s1")
        )
        policy = BudgetPolicy(max_cost_usd=10.0, warn_at_percent=80.0)
        hook = make_budget_hook(tracker, policy)
        result = await hook(_make_input(), "tu1", None)
        assert "systemMessage" in result
        assert "Budget warning" in result["systemMessage"]

    @pytest.mark.asyncio
    async def test_warn_only_action(self, tracker_with_cost):
        policy = BudgetPolicy(max_cost_usd=5.0, action_on_limit="warn")
        hook = make_budget_hook(tracker_with_cost, policy)
        result = await hook(_make_input(), "tu1", None)
        assert "systemMessage" in result
        assert "hookSpecificOutput" not in result  # Does not deny

    @pytest.mark.asyncio
    async def test_calls_on_limit_callback(self, tracker_with_cost):
        received = []
        policy = BudgetPolicy(max_cost_usd=5.0, action_on_limit="stop")
        hook = make_budget_hook(
            tracker_with_cost, policy, on_limit=lambda c, m: received.append((c, m))
        )
        await hook(_make_input(), "tu1", None)
        assert len(received) == 1
        assert received[0][1] == 5.0

    @pytest.mark.asyncio
    async def test_calls_on_warning_callback(self):
        tracker = CostTracker()
        tracker.record(
            CostEvent.create(model="s", tool_name="t", cost_usd=8.5, session_id="s1")
        )
        received = []
        policy = BudgetPolicy(max_cost_usd=10.0, warn_at_percent=80.0)
        hook = make_budget_hook(
            tracker, policy, on_warning=lambda c, m: received.append((c, m))
        )
        await hook(_make_input(), "tu1", None)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_ignores_non_pretooluse(self):
        tracker = CostTracker()
        policy = BudgetPolicy(max_cost_usd=0.01)
        tracker.record(
            CostEvent.create(model="s", tool_name="t", cost_usd=1.0, session_id="s1")
        )
        hook = make_budget_hook(tracker, policy)
        result = await hook({"hook_event_name": "PostToolUse"}, "tu1", None)
        assert result == {}


class TestStopHook:
    @pytest.mark.asyncio
    async def test_calls_callback_on_stop(self):
        tracker = CostTracker()
        tracker.record(
            CostEvent.create(model="s", tool_name="t", cost_usd=1.5, session_id="s1")
        )
        received = []
        hook = make_stop_hook(tracker, on_session_end=lambda sid, cost: received.append((sid, cost)))
        await hook(
            {"hook_event_name": "Stop", "session_id": "s1"},
            "",
            None,
        )
        assert len(received) == 1
        assert received[0] == ("s1", 1.5)

    @pytest.mark.asyncio
    async def test_handles_subagent_stop(self):
        tracker = CostTracker()
        tracker.record(
            CostEvent.create(model="s", tool_name="t", cost_usd=0.5, session_id="s1")
        )
        received = []
        hook = make_stop_hook(tracker, on_session_end=lambda sid, cost: received.append((sid, cost)))
        await hook(
            {"hook_event_name": "SubagentStop", "session_id": "s1"},
            "",
            None,
        )
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_ignores_other_events(self):
        tracker = CostTracker()
        received = []
        hook = make_stop_hook(tracker, on_session_end=lambda sid, cost: received.append((sid, cost)))
        await hook({"hook_event_name": "PreToolUse"}, "", None)
        assert len(received) == 0
