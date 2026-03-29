"""Model pricing registry for real-time cost estimation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelPricing:
    """Pricing for a single model."""

    input_per_million: float
    output_per_million: float
    cache_read_per_million: float | None = None
    cache_creation_per_million: float | None = None

    def __post_init__(self) -> None:
        if self.cache_read_per_million is None:
            self.cache_read_per_million = self.input_per_million * 0.1
        if self.cache_creation_per_million is None:
            self.cache_creation_per_million = self.input_per_million * 1.25


# Default Claude model pricing (March 2026)
_DEFAULT_MODELS: dict[str, ModelPricing] = {
    # Haiku 4.5
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_million=1.00,
        output_per_million=5.00,
    ),
    # Sonnet 4.6
    "claude-sonnet-4-6-20250514": ModelPricing(
        input_per_million=3.00,
        output_per_million=15.00,
    ),
    # Opus 4.6
    "claude-opus-4-6-20250514": ModelPricing(
        input_per_million=5.00,
        output_per_million=25.00,
    ),
}

# Aliases that map to canonical model IDs
_MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6-20250514",
    "claude-sonnet-4-6": "claude-sonnet-4-6-20250514",
    "opus": "claude-opus-4-6-20250514",
    "claude-opus-4-6": "claude-opus-4-6-20250514",
}


@dataclass
class PricingRegistry:
    """Registry of model pricing for cost estimation.

    Comes pre-loaded with Claude model prices. Custom models can be registered.
    """

    _models: dict[str, ModelPricing] = field(default_factory=lambda: dict(_DEFAULT_MODELS))
    _aliases: dict[str, str] = field(default_factory=lambda: dict(_MODEL_ALIASES))

    def register(
        self,
        model_name: str,
        input_per_million: float,
        output_per_million: float,
        cache_read_per_million: float | None = None,
        cache_creation_per_million: float | None = None,
    ) -> None:
        """Register pricing for a custom model."""
        self._models[model_name] = ModelPricing(
            input_per_million=input_per_million,
            output_per_million=output_per_million,
            cache_read_per_million=cache_read_per_million,
            cache_creation_per_million=cache_creation_per_million,
        )

    def add_alias(self, alias: str, model_name: str) -> None:
        """Add a short alias for a model name."""
        self._aliases[alias] = model_name

    def _resolve(self, model: str) -> ModelPricing | None:
        """Resolve a model name (or alias) to its pricing."""
        if model in self._models:
            return self._models[model]
        canonical = self._aliases.get(model)
        if canonical and canonical in self._models:
            return self._models[canonical]
        # Try prefix matching for versioned model strings
        for key in self._models:
            if model.startswith(key) or key.startswith(model):
                return self._models[key]
        return None

    def estimate_cost(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Estimate cost in USD for the given token counts.

        Returns 0.0 if the model is not recognized.
        """
        pricing = self._resolve(model)
        if pricing is None:
            return 0.0

        cost = 0.0
        cost += (input_tokens / 1_000_000) * pricing.input_per_million
        cost += (output_tokens / 1_000_000) * pricing.output_per_million
        if cache_read_tokens and pricing.cache_read_per_million is not None:
            cost += (cache_read_tokens / 1_000_000) * pricing.cache_read_per_million
        if cache_creation_tokens and pricing.cache_creation_per_million is not None:
            cost += (cache_creation_tokens / 1_000_000) * pricing.cache_creation_per_million
        return cost

    def get_pricing(self, model: str) -> ModelPricing | None:
        """Get pricing for a model. Returns None if not found."""
        return self._resolve(model)

    @property
    def supported_models(self) -> list[str]:
        """List all registered model names."""
        return list(self._models.keys())


# Singleton default registry
default_registry = PricingRegistry()
