"""Tests for budget policy."""

import pytest

from argos_budget_guardian.core.budget import BudgetPolicy


class TestBudgetPolicy:
    def test_defaults(self):
        p = BudgetPolicy(max_cost_usd=10.0)
        assert p.warn_at_percent == 80.0
        assert p.action_on_limit == "stop"
        assert p.scope == "session"
        assert p.cooldown_seconds == 0

    def test_warn_threshold(self):
        p = BudgetPolicy(max_cost_usd=10.0, warn_at_percent=75.0)
        assert p.warn_threshold_usd == 7.5

    def test_is_over_budget(self):
        p = BudgetPolicy(max_cost_usd=5.0)
        assert not p.is_over_budget(4.99)
        assert p.is_over_budget(5.0)
        assert p.is_over_budget(5.01)

    def test_is_at_warning(self):
        p = BudgetPolicy(max_cost_usd=10.0, warn_at_percent=80.0)
        assert not p.is_at_warning(7.99)
        assert p.is_at_warning(8.0)
        assert p.is_at_warning(9.99)
        assert not p.is_at_warning(10.0)  # Over budget, not warning

    def test_utilization_percent(self):
        p = BudgetPolicy(max_cost_usd=10.0)
        assert p.utilization_percent(0) == 0.0
        assert p.utilization_percent(5.0) == 50.0
        assert p.utilization_percent(10.0) == 100.0
        assert p.utilization_percent(15.0) == 100.0  # Capped at 100

    def test_invalid_max_cost(self):
        with pytest.raises(ValueError, match="must be positive"):
            BudgetPolicy(max_cost_usd=0)

    def test_invalid_warn_percent(self):
        with pytest.raises(ValueError, match="between 0 and 100"):
            BudgetPolicy(max_cost_usd=10.0, warn_at_percent=0)

    def test_invalid_cooldown(self):
        with pytest.raises(ValueError, match="non-negative"):
            BudgetPolicy(max_cost_usd=10.0, cooldown_seconds=-1)
