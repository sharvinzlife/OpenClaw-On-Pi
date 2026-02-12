"""Unit tests for model getter/setter on BaseProvider and ProviderManager.

Tests Task 6.1: model selection backend methods.
Requirements: 1.1, 1.3
"""

from unittest.mock import MagicMock

import pytest

from src.llm.base_provider import BaseProvider
from src.llm.provider_manager import ProviderManager
from src.llm.rate_limiter import RateLimiter, RateLimitConfig


class ConcreteProvider(BaseProvider):
    """Minimal concrete provider for testing (BaseProvider is abstract)."""

    def __init__(self, name: str, models: list[str], default_model: str):
        super().__init__(config={})
        self.name = name
        self._available_models = models
        self._default_model = default_model

    async def generate(self, messages, model=None):
        raise NotImplementedError

    async def stream(self, messages, model=None):
        raise NotImplementedError

    async def health_check(self):
        return True

    def get_available_models(self):
        return list(self._available_models)


def _make_provider_manager(*providers: BaseProvider) -> ProviderManager:
    """Build a ProviderManager from a list of providers."""
    provider_dict = {p.name: p for p in providers}
    limiter = RateLimiter({
        p.name: RateLimitConfig(requests_per_minute=1000, tokens_per_minute=1_000_000)
        for p in providers
    })
    return ProviderManager(providers=provider_dict, rate_limiter=limiter)


# --- BaseProvider tests ---

class TestBaseProviderCurrentModel:
    def test_returns_default_model(self):
        p = ConcreteProvider("groq", ["m1", "m2"], "m1")
        assert p.current_model == "m1"

    def test_reflects_set_model(self):
        p = ConcreteProvider("groq", ["m1", "m2"], "m1")
        p.set_model("m2")
        assert p.current_model == "m2"


class TestBaseProviderSetModel:
    def test_valid_model_returns_true(self):
        p = ConcreteProvider("groq", ["m1", "m2"], "m1")
        assert p.set_model("m2") is True
        assert p.current_model == "m2"

    def test_invalid_model_returns_false(self):
        p = ConcreteProvider("groq", ["m1", "m2"], "m1")
        assert p.set_model("nonexistent") is False
        # Model should remain unchanged
        assert p.current_model == "m1"

    def test_empty_available_models(self):
        p = ConcreteProvider("groq", [], "")
        assert p.set_model("anything") is False


# --- ProviderManager tests ---

class TestProviderManagerGetAllModels:
    def test_returns_all_providers(self):
        pm = _make_provider_manager(
            ConcreteProvider("groq", ["a", "b"], "a"),
            ConcreteProvider("ollama", ["x"], "x"),
        )
        result = pm.get_all_models()
        assert set(result.keys()) == {"groq", "ollama"}

    def test_models_and_current(self):
        pm = _make_provider_manager(
            ConcreteProvider("groq", ["a", "b"], "a"),
        )
        info = pm.get_all_models()["groq"]
        assert info["models"] == ["a", "b"]
        assert info["current"] == "a"

    def test_empty_providers(self):
        limiter = RateLimiter({})
        pm = ProviderManager(providers={}, rate_limiter=limiter)
        assert pm.get_all_models() == {}


class TestProviderManagerSetProviderModel:
    def test_valid_provider_and_model(self):
        pm = _make_provider_manager(
            ConcreteProvider("groq", ["a", "b"], "a"),
        )
        assert pm.set_provider_model("groq", "b") is True
        assert pm.get_all_models()["groq"]["current"] == "b"

    def test_unknown_provider(self):
        pm = _make_provider_manager(
            ConcreteProvider("groq", ["a"], "a"),
        )
        assert pm.set_provider_model("nonexistent", "a") is False

    def test_invalid_model_for_provider(self):
        pm = _make_provider_manager(
            ConcreteProvider("groq", ["a", "b"], "a"),
        )
        assert pm.set_provider_model("groq", "z") is False
        # Model should remain unchanged
        assert pm.get_all_models()["groq"]["current"] == "a"
