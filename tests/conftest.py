"""Shared test fixtures."""

from __future__ import annotations

import pytest

from argos_budget_guardian.core.budget import BudgetPolicy
from argos_budget_guardian.core.pricing import PricingRegistry
from argos_budget_guardian.core.tracker import CostEvent, CostTracker


@pytest.fixture
def tracker() -> CostTracker:
    return CostTracker()


@pytest.fixture
def registry() -> PricingRegistry:
    return PricingRegistry()


@pytest.fixture
def default_policy() -> BudgetPolicy:
    return BudgetPolicy(max_cost_usd=10.0)


@pytest.fixture
def sample_event() -> CostEvent:
    return CostEvent.create(
        model="claude-sonnet-4-6-20250514",
        tool_name="Write",
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=200,
        cache_creation_tokens=0,
        cost_usd=0.0105,
        session_id="test-session-1",
    )


@pytest.fixture
def sample_events() -> list[CostEvent]:
    return [
        CostEvent.create(
            model="claude-sonnet-4-6-20250514",
            tool_name="Read",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.003,
            session_id="test-session-1",
        ),
        CostEvent.create(
            model="claude-sonnet-4-6-20250514",
            tool_name="Write",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0105,
            session_id="test-session-1",
        ),
        CostEvent.create(
            model="claude-haiku-4-5-20251001",
            tool_name="Bash",
            input_tokens=200,
            output_tokens=50,
            cost_usd=0.00045,
            session_id="test-session-1",
        ),
    ]
