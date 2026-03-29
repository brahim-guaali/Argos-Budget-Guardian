"""Tests for the pricing registry."""

from argos_budget_guardian.core.pricing import ModelPricing, default_registry


class TestModelPricing:
    def test_defaults_cache_pricing(self):
        p = ModelPricing(input_per_million=3.0, output_per_million=15.0)
        assert abs(p.cache_read_per_million - 0.3) < 1e-10  # 10% of input
        assert abs(p.cache_creation_per_million - 3.75) < 1e-10  # 125% of input

    def test_explicit_cache_pricing(self):
        p = ModelPricing(
            input_per_million=3.0,
            output_per_million=15.0,
            cache_read_per_million=0.5,
            cache_creation_per_million=4.0,
        )
        assert p.cache_read_per_million == 0.5
        assert p.cache_creation_per_million == 4.0


class TestPricingRegistry:
    def test_estimate_sonnet(self, registry):
        cost = registry.estimate_cost(
            model="claude-sonnet-4-6-20250514",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost == 3.0  # $3/M input tokens

    def test_estimate_output(self, registry):
        cost = registry.estimate_cost(
            model="claude-sonnet-4-6-20250514",
            input_tokens=0,
            output_tokens=1_000_000,
        )
        assert cost == 15.0  # $15/M output tokens

    def test_estimate_haiku(self, registry):
        cost = registry.estimate_cost(
            model="claude-haiku-4-5-20251001",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == 6.0  # $1 + $5

    def test_estimate_opus(self, registry):
        cost = registry.estimate_cost(
            model="claude-opus-4-6-20250514",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == 30.0  # $5 + $25

    def test_alias_resolution(self, registry):
        cost_alias = registry.estimate_cost("sonnet", input_tokens=1000, output_tokens=500)
        cost_full = registry.estimate_cost(
            "claude-sonnet-4-6-20250514", input_tokens=1000, output_tokens=500
        )
        assert cost_alias == cost_full

    def test_unknown_model_returns_zero(self, registry):
        cost = registry.estimate_cost("unknown-model", input_tokens=1000)
        assert cost == 0.0

    def test_register_custom_model(self, registry):
        registry.register("my-model", input_per_million=2.0, output_per_million=10.0)
        cost = registry.estimate_cost("my-model", input_tokens=1_000_000)
        assert cost == 2.0

    def test_cache_tokens(self, registry):
        cost = registry.estimate_cost(
            model="claude-sonnet-4-6-20250514",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,
        )
        assert abs(cost - 0.3) < 1e-10  # 10% of $3

    def test_supported_models(self, registry):
        models = registry.supported_models
        assert len(models) == 3
        assert "claude-sonnet-4-6-20250514" in models

    def test_default_registry_is_populated(self):
        assert len(default_registry.supported_models) == 3

    def test_small_token_count(self, registry):
        cost = registry.estimate_cost(
            model="claude-sonnet-4-6-20250514",
            input_tokens=100,
            output_tokens=50,
        )
        expected = (100 / 1_000_000) * 3.0 + (50 / 1_000_000) * 15.0
        assert abs(cost - expected) < 1e-10
