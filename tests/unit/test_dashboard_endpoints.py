"""Unit tests for dashboard API endpoints.

Tests Task 6.2: /api/models and /api/model endpoints.
Requirements: 1.1, 1.2, 1.3
"""

import json

import pytest

from src.llm.base_provider import BaseProvider
from src.llm.provider_manager import ProviderManager
from src.llm.rate_limiter import RateLimiter, RateLimitConfig
from src.web.dashboard import create_dashboard_app, DashboardState


class ConcreteProvider(BaseProvider):
    """Minimal concrete provider for testing."""

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


def _make_pm(*providers: BaseProvider) -> ProviderManager:
    provider_dict = {p.name: p for p in providers}
    limiter = RateLimiter({
        p.name: RateLimitConfig(requests_per_minute=1000, tokens_per_minute=1_000_000)
        for p in providers
    })
    return ProviderManager(providers=provider_dict, rate_limiter=limiter)


@pytest.fixture
def app_with_pm():
    """Flask test client with a ProviderManager wired in."""
    pm = _make_pm(
        ConcreteProvider("groq", ["llama-70b", "llama-8b"], "llama-70b"),
        ConcreteProvider("ollama", ["mistral"], "mistral"),
    )
    app = create_dashboard_app(state=DashboardState(), provider_manager=pm)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, pm


@pytest.fixture
def app_without_pm():
    """Flask test client with no ProviderManager."""
    app = create_dashboard_app(state=DashboardState(), provider_manager=None)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# --- GET /api/models ---

class TestGetModels:
    def test_returns_all_providers(self, app_with_pm):
        client, _ = app_with_pm
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert set(data["providers"].keys()) == {"groq", "ollama"}

    def test_returns_models_and_current(self, app_with_pm):
        client, _ = app_with_pm
        data = client.get("/api/models").get_json()
        groq = data["providers"]["groq"]
        assert groq["models"] == ["llama-70b", "llama-8b"]
        assert groq["current"] == "llama-70b"

    def test_503_when_no_provider_manager(self, app_without_pm):
        resp = app_without_pm.get("/api/models")
        assert resp.status_code == 503


# --- POST /api/model ---

class TestSetModel:
    def test_set_valid_model(self, app_with_pm):
        client, pm = app_with_pm
        resp = client.post(
            "/api/model",
            data=json.dumps({"provider": "groq", "model": "llama-8b"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["provider"] == "groq"
        assert data["model"] == "llama-8b"
        # Verify it actually changed
        models = client.get("/api/models").get_json()
        assert models["providers"]["groq"]["current"] == "llama-8b"

    def test_invalid_model_returns_400(self, app_with_pm):
        client, _ = app_with_pm
        resp = client.post(
            "/api/model",
            data=json.dumps({"provider": "groq", "model": "nonexistent"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_invalid_provider_returns_400(self, app_with_pm):
        client, _ = app_with_pm
        resp = client.post(
            "/api/model",
            data=json.dumps({"provider": "nope", "model": "llama-70b"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_missing_body_returns_400(self, app_with_pm):
        client, _ = app_with_pm
        resp = client.post("/api/model", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_fields_returns_400(self, app_with_pm):
        client, _ = app_with_pm
        resp = client.post(
            "/api/model",
            data=json.dumps({"provider": "groq"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_503_when_no_provider_manager(self, app_without_pm):
        resp = app_without_pm.post(
            "/api/model",
            data=json.dumps({"provider": "groq", "model": "llama-70b"}),
            content_type="application/json",
        )
        assert resp.status_code == 503
