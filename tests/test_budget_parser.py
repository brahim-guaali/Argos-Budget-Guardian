"""Tests for natural language budget parser."""

import pytest

from argos_budget_guardian.nlp.budget_parser import parse_budget


class TestBudgetParser:
    def test_simple_dollar_amount(self):
        p = parse_budget("$5")
        assert p.max_cost_usd == 5.0
        assert p.scope == "session"

    def test_dollar_with_cents(self):
        p = parse_budget("$10.50")
        assert p.max_cost_usd == 10.50

    def test_without_dollar_sign(self):
        p = parse_budget("5.00")
        assert p.max_cost_usd == 5.0

    def test_daily_scope(self):
        p = parse_budget("$10 per day")
        assert p.max_cost_usd == 10.0
        assert p.scope == "daily"

    def test_today_scope(self):
        p = parse_budget("spend no more than $5 today")
        assert p.max_cost_usd == 5.0
        assert p.scope == "daily"

    def test_global_scope(self):
        p = parse_budget("$20 total")
        assert p.max_cost_usd == 20.0
        assert p.scope == "global"

    def test_lifetime_scope(self):
        p = parse_budget("$100 lifetime")
        assert p.max_cost_usd == 100.0
        assert p.scope == "global"

    def test_warn_action(self):
        p = parse_budget("$5 per day, warn only")
        assert p.action_on_limit == "warn"
        assert p.scope == "daily"

    def test_pause_action(self):
        p = parse_budget("$10, pause when exceeded")
        assert p.action_on_limit == "pause"

    def test_stop_action(self):
        p = parse_budget("$5 stop")
        assert p.action_on_limit == "stop"

    def test_default_action_is_stop(self):
        p = parse_budget("$5")
        assert p.action_on_limit == "stop"

    def test_no_amount_raises(self):
        with pytest.raises(ValueError, match="Could not find a dollar amount"):
            parse_budget("no budget here")

    def test_complex_sentence(self):
        p = parse_budget("I want to spend no more than $7.50 per day and just warn me")
        assert p.max_cost_usd == 7.50
        assert p.scope == "daily"
        assert p.action_on_limit == "warn"
