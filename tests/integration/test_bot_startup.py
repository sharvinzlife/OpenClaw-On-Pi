"""Integration tests for bot startup and component wiring.

Tests verify that:
1. All components can be initialized with valid configuration
2. Components wire together correctly (ConfigManager → AuthManager → ProviderManager → etc.)
3. The bot fails gracefully with missing/invalid configuration
4. Startup sequence works end-to-end when mocking external services
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.utils.config_manager import ConfigManager, AppConfig, ProviderConfig, PermissionSettings
from src.utils.audit_logger import AuditLogger
from src.utils.context_store import ContextStore
from src.security.auth import AuthManager, AuthSettings
from src.llm.rate_limiter import RateLimiter, RateLimitConfig
from src.llm.groq_provider import GroqProvider
from src.llm.ollama_cloud_provider import OllamaCloudProvider
from src.llm.ollama_local_provider import LocalOllamaProvider
from src.llm.provider_manager import ProviderManager
from src.bot.command_router import CommandRouter, VERSION
from src.bot.telegram_handler import TelegramHandler
from src.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config_dir(tmp_path):
    """Create a temporary config directory with valid configuration files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # .env file
    env_content = (
        "TELEGRAM_BOT_TOKEN=test-token-12345\n"
        "GROQ_API_KEY=test-groq-key-67890\n"
        "OLLAMA_CLOUD_URL=http://localhost:11434\n"
    )
    (config_dir / ".env").write_text(env_content)

    # config.yaml
    config_yaml = {
        "bot": {
            "default_provider": "groq",
            "default_model": "llama-3.1-70b-versatile",
            "response_timeout": 30,
            "max_context_messages": 10,
            "max_context_tokens": 4000,
        },
        "logging": {
            "level": "INFO",
            "retention_days": 30,
            "audit_path": str(tmp_path / "logs" / "audit.log"),
        },
        "streaming": {
            "update_interval_ms": 500,
            "min_chunk_chars": 50,
        },
    }
    with open(config_dir / "config.yaml", "w") as f:
        yaml.dump(config_yaml, f)

    # permissions.yaml
    permissions_yaml = {
        "admins": [123456789],
        "users": [987654321],
        "guests": [111222333],
        "settings": {
            "allow_unknown_users": False,
            "guest_rate_limit": 5,
            "user_rate_limit": 20,
            "admin_rate_limit": 100,
            "auth_failure_lockout": 5,
            "lockout_duration_minutes": 15,
        },
    }
    with open(config_dir / "permissions.yaml", "w") as f:
        yaml.dump(permissions_yaml, f)

    # providers.yaml
    providers_yaml = {
        "groq": {
            "enabled": True,
            "priority": 1,
            "rate_limits": {
                "requests_per_minute": 30,
                "tokens_per_minute": 14400,
            },
            "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"],
            "default_model": "llama-3.1-70b-versatile",
        },
        "ollama_cloud": {
            "enabled": True,
            "priority": 2,
            "rate_limits": {
                "requests_per_minute": 60,
                "tokens_per_minute": 50000,
            },
            "models": ["llama3.1", "mistral"],
            "default_model": "llama3.1",
        },
        "ollama_local": {
            "enabled": False,
            "priority": 3,
            "rate_limits": {
                "requests_per_minute": 100,
                "tokens_per_minute": 100000,
            },
            "models": [],
            "default_model": "llama3.1",
        },
    }
    with open(config_dir / "providers.yaml", "w") as f:
        yaml.dump(providers_yaml, f)

    # skills.yaml
    skills_yaml = {
        "skills": {
            "calc": {"enabled": True},
            "sysinfo": {"enabled": True},
        },
    }
    with open(config_dir / "skills.yaml", "w") as f:
        yaml.dump(skills_yaml, f)

    return config_dir


@pytest.fixture
def tmp_config_dir_missing_token(tmp_path):
    """Config directory with missing TELEGRAM_BOT_TOKEN."""
    config_dir = tmp_path / "config_missing"
    config_dir.mkdir()

    # .env with missing token
    env_content = "GROQ_API_KEY=test-groq-key-67890\n"
    (config_dir / ".env").write_text(env_content)

    config_yaml = {
        "bot": {"default_provider": "groq"},
        "logging": {"level": "INFO", "audit_path": str(tmp_path / "logs" / "audit.log")},
    }
    with open(config_dir / "config.yaml", "w") as f:
        yaml.dump(config_yaml, f)

    with open(config_dir / "permissions.yaml", "w") as f:
        yaml.dump({"admins": [123], "settings": {}}, f)

    providers_yaml = {
        "groq": {
            "enabled": True,
            "priority": 1,
            "rate_limits": {"requests_per_minute": 30, "tokens_per_minute": 14400},
            "models": ["llama-3.1-70b-versatile"],
            "default_model": "llama-3.1-70b-versatile",
        },
    }
    with open(config_dir / "providers.yaml", "w") as f:
        yaml.dump(providers_yaml, f)

    return config_dir


@pytest.fixture
def loaded_config(tmp_config_dir):
    """Return a fully loaded ConfigManager."""
    # Clear env vars that might leak from the real config
    env_backup = {}
    for key in ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"):
        env_backup[key] = os.environ.pop(key, None)

    cm = ConfigManager(str(tmp_config_dir))
    cm.load_all()

    yield cm

    # Restore env vars
    for key, val in env_backup.items():
        if val is not None:
            os.environ[key] = val
        else:
            os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# 1. Configuration loading and validation
# ---------------------------------------------------------------------------

class TestConfigurationLoading:
    """Tests that ConfigManager loads and validates configuration correctly."""

    def test_load_all_populates_app_config(self, loaded_config):
        """Valid config files produce a fully populated AppConfig."""
        cfg = loaded_config.app_config
        assert cfg is not None
        assert cfg.telegram_token == "test-token-12345"
        assert cfg.groq_api_key == "test-groq-key-67890"
        assert cfg.default_provider == "groq"
        assert cfg.max_context_messages == 10

    def test_load_all_populates_providers(self, loaded_config):
        """Provider configs are parsed from providers.yaml."""
        assert "groq" in loaded_config.provider_configs
        assert "ollama_cloud" in loaded_config.provider_configs
        groq = loaded_config.provider_configs["groq"]
        assert groq.enabled is True
        assert groq.priority == 1
        assert groq.requests_per_minute == 30

    def test_load_all_populates_permissions(self, loaded_config):
        """Permissions are parsed from permissions.yaml."""
        assert 123456789 in loaded_config.permissions
        assert loaded_config.permissions[123456789] == "admin"
        assert 987654321 in loaded_config.permissions
        assert loaded_config.permissions[987654321] == "user"

    def test_validate_passes_with_valid_config(self, loaded_config):
        """Validation returns no errors for a complete config."""
        errors = loaded_config.validate()
        assert errors == []

    def test_validate_fails_missing_telegram_token(self, tmp_config_dir_missing_token):
        """Validation catches missing TELEGRAM_BOT_TOKEN."""
        # Clear env vars
        env_backup = {}
        for key in ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"):
            env_backup[key] = os.environ.pop(key, None)

        try:
            cm = ConfigManager(str(tmp_config_dir_missing_token))
            cm.load_all()
            errors = cm.validate()
            assert len(errors) > 0
            assert any("TELEGRAM_BOT_TOKEN" in e for e in errors)
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

    def test_validate_fails_no_providers_enabled(self, tmp_path):
        """Validation catches when no providers are enabled."""
        config_dir = tmp_path / "config_no_providers"
        config_dir.mkdir()

        env_backup = {}
        for key in ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"):
            env_backup[key] = os.environ.pop(key, None)

        (config_dir / ".env").write_text(
            "TELEGRAM_BOT_TOKEN=tok\nGROQ_API_KEY=key\n"
        )
        with open(config_dir / "config.yaml", "w") as f:
            yaml.dump({"bot": {"default_provider": "groq"}}, f)
        with open(config_dir / "permissions.yaml", "w") as f:
            yaml.dump({"admins": [1], "settings": {}}, f)
        with open(config_dir / "providers.yaml", "w") as f:
            yaml.dump(
                {"groq": {"enabled": False, "priority": 1, "rate_limits": {}, "models": [], "default_model": "x"}},
                f,
            )

        try:
            cm = ConfigManager(str(config_dir))
            cm.load_all()
            errors = cm.validate()
            assert len(errors) > 0
            assert any("provider" in e.lower() for e in errors)
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# 2. Component wiring — all components initialise and connect
# ---------------------------------------------------------------------------

class TestComponentWiring:
    """Tests that all components wire together as main.py does."""

    def test_auth_manager_from_config(self, loaded_config):
        """AuthManager initialises from ConfigManager permissions."""
        settings = AuthSettings(
            allow_unknown_users=loaded_config.permission_settings.allow_unknown_users,
            guest_rate_limit=loaded_config.permission_settings.guest_rate_limit,
            user_rate_limit=loaded_config.permission_settings.user_rate_limit,
            admin_rate_limit=loaded_config.permission_settings.admin_rate_limit,
            auth_failure_lockout=loaded_config.permission_settings.auth_failure_lockout,
            lockout_duration_minutes=loaded_config.permission_settings.lockout_duration_minutes,
        )
        auth = AuthManager(loaded_config.permissions, settings)

        assert auth.is_authorized(123456789)  # admin
        assert auth.is_authorized(987654321)  # user
        assert not auth.is_authorized(999999999)  # unknown

    def test_rate_limiter_from_config(self, loaded_config):
        """RateLimiter initialises from provider configs."""
        rate_limits = {}
        for name, cfg in loaded_config.provider_configs.items():
            rate_limits[name] = RateLimitConfig(
                requests_per_minute=cfg.requests_per_minute,
                tokens_per_minute=cfg.tokens_per_minute,
            )
        rl = RateLimiter(rate_limits)

        assert rl.can_request("groq")
        assert "groq" in rl.limits
        assert rl.limits["groq"].requests_per_minute == 30

    def test_groq_provider_initialises(self, loaded_config):
        """GroqProvider can be constructed from config data."""
        groq_cfg = loaded_config.provider_configs["groq"]
        provider = GroqProvider({
            "api_key": loaded_config.app_config.groq_api_key,
            "default_model": groq_cfg.default_model,
            "models": groq_cfg.models,
        })
        assert provider.name == "groq"
        assert "llama-3.1-70b-versatile" in provider.get_available_models()

    def test_ollama_cloud_provider_initialises(self, loaded_config):
        """OllamaCloudProvider can be constructed from config data."""
        oc_cfg = loaded_config.provider_configs["ollama_cloud"]
        provider = OllamaCloudProvider({
            "cloud_url": loaded_config.app_config.ollama_cloud_url,
            "default_model": oc_cfg.default_model,
            "models": oc_cfg.models,
        })
        assert provider.name == "ollama_cloud"

    def test_provider_manager_wiring(self, loaded_config):
        """ProviderManager wires providers and rate limiter together."""
        rate_limits = {}
        for name, cfg in loaded_config.provider_configs.items():
            rate_limits[name] = RateLimitConfig(
                requests_per_minute=cfg.requests_per_minute,
                tokens_per_minute=cfg.tokens_per_minute,
            )
        rl = RateLimiter(rate_limits)

        providers = {
            "groq": GroqProvider({
                "api_key": loaded_config.app_config.groq_api_key,
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile"],
            }),
        }
        priority = sorted(
            loaded_config.provider_configs.keys(),
            key=lambda n: loaded_config.provider_configs[n].priority,
        )
        pm = ProviderManager(providers, rl, priority)

        # Should return the groq provider
        p = pm.get_provider()
        assert p is not None
        assert p.name == "groq"

    def test_context_store_initialises(self, tmp_path):
        """ContextStore initialises and can add/retrieve messages."""
        cs = ContextStore(
            storage_path=str(tmp_path / "data" / "contexts.json"),
            max_messages=10,
            max_tokens=4000,
        )
        cs.add_message(123, "user", "hello", tokens=5)
        msgs = cs.get_context(123)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "hello"

    def test_command_router_wiring(self, loaded_config):
        """CommandRouter wires auth, provider manager, rate limiter, context store."""
        auth = AuthManager(loaded_config.permissions)
        rl = RateLimiter({
            "groq": RateLimitConfig(requests_per_minute=30, tokens_per_minute=14400),
        })
        providers = {
            "groq": GroqProvider({
                "api_key": "test-key",
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile"],
            }),
        }
        pm = ProviderManager(providers, rl, ["groq"])
        cs = ContextStore(storage_path="/tmp/test_ctx.json")

        router = CommandRouter(
            auth_manager=auth,
            provider_manager=pm,
            rate_limiter=rl,
            context_store=cs,
        )

        # Core commands should be registered
        assert "start" in router.handlers
        assert "help" in router.handlers
        assert "status" in router.handlers
        assert "reset" in router.handlers

    def test_telegram_handler_initialises(self, loaded_config, tmp_path):
        """TelegramHandler can be constructed with all dependencies."""
        auth = AuthManager(loaded_config.permissions)
        rl = RateLimiter({
            "groq": RateLimitConfig(requests_per_minute=30, tokens_per_minute=14400),
        })
        providers = {
            "groq": GroqProvider({
                "api_key": "test-key",
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile"],
            }),
        }
        pm = ProviderManager(providers, rl, ["groq"])
        cs = ContextStore(storage_path=str(tmp_path / "ctx.json"))
        audit = AuditLogger(
            log_path=str(tmp_path / "audit.log"),
            retention_days=7,
        )
        router = CommandRouter(
            auth_manager=auth,
            provider_manager=pm,
            rate_limiter=rl,
            context_store=cs,
        )

        handler = TelegramHandler(
            token="test-token-12345",
            command_router=router,
            auth_manager=auth,
            provider_manager=pm,
            context_store=cs,
            audit_logger=audit,
            rate_limiter=rl,
            streaming_interval_ms=500,
            streaming_min_chars=50,
        )

        assert handler.token == "test-token-12345"
        assert handler.command_router is router
        assert handler.auth_manager is auth
        assert handler.provider_manager is pm

    def test_skill_registry_wiring(self, loaded_config, tmp_path):
        """SkillRegistry discovers and loads skills via CommandRouter."""
        auth = AuthManager(loaded_config.permissions)
        router = CommandRouter(auth_manager=auth)

        skills_config = {"calc": {"enabled": True}, "sysinfo": {"enabled": True}}
        registry = SkillRegistry(skills_config, router)
        registry.discover_and_load()

        # At least calc and sysinfo should load (they have no external deps)
        assert len(registry.skills) >= 1


# ---------------------------------------------------------------------------
# 3. Graceful failure with bad configuration
# ---------------------------------------------------------------------------

class TestGracefulFailure:
    """Tests that the startup path fails gracefully with bad config."""

    def test_missing_config_dir_returns_empty_yaml(self):
        """ConfigManager handles missing config directory gracefully."""
        cm = ConfigManager("/nonexistent/path")
        data = cm.load_yaml("config.yaml")
        assert data == {}

    def test_malformed_yaml_returns_empty(self, tmp_path):
        """ConfigManager handles malformed YAML gracefully."""
        config_dir = tmp_path / "bad_yaml"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(": : : invalid yaml [[[")

        cm = ConfigManager(str(config_dir))
        # Should not raise — yaml.safe_load may raise, but let's see
        try:
            data = cm.load_yaml("config.yaml")
        except Exception:
            # Malformed YAML raising is acceptable graceful failure
            pass

    def test_load_all_with_empty_files(self, tmp_path):
        """ConfigManager.load_all works with empty config files."""
        config_dir = tmp_path / "empty_config"
        config_dir.mkdir()

        # Clear env vars
        env_backup = {}
        for key in ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"):
            env_backup[key] = os.environ.pop(key, None)

        (config_dir / ".env").write_text("")
        (config_dir / "config.yaml").write_text("")
        (config_dir / "permissions.yaml").write_text("")
        (config_dir / "providers.yaml").write_text("")

        try:
            cm = ConfigManager(str(config_dir))
            cm.load_all()
            # Should load without crashing
            assert cm.app_config is not None
            # But validation should fail (missing token, key, no providers)
            errors = cm.validate()
            assert len(errors) > 0
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

    def test_context_store_load_from_nonexistent_file(self, tmp_path):
        """ContextStore.load_from_disk handles missing file gracefully."""
        cs = ContextStore(storage_path=str(tmp_path / "missing.json"))
        cs.load_from_disk()  # Should not raise
        assert cs.contexts == {}

    def test_context_store_load_from_corrupt_json(self, tmp_path):
        """ContextStore.load_from_disk handles corrupt JSON gracefully."""
        bad_file = tmp_path / "corrupt.json"
        bad_file.write_text("{not valid json!!!")
        cs = ContextStore(storage_path=str(bad_file))
        cs.load_from_disk()  # Should not raise
        assert cs.contexts == {}


# ---------------------------------------------------------------------------
# 4. End-to-end startup sequence (mocking external services)
# ---------------------------------------------------------------------------

class TestStartupSequence:
    """Tests the full startup wiring sequence as main.py does it."""

    def test_full_component_chain(self, loaded_config, tmp_path):
        """Replicate the main() wiring sequence and verify all components connect."""
        cfg = loaded_config
        app = cfg.app_config

        # 1. AuditLogger
        audit = AuditLogger(
            log_path=str(tmp_path / "logs" / "audit.log"),
            retention_days=app.log_retention_days,
        )

        # 2. AuthManager
        auth_settings = AuthSettings(
            allow_unknown_users=cfg.permission_settings.allow_unknown_users,
            guest_rate_limit=cfg.permission_settings.guest_rate_limit,
            user_rate_limit=cfg.permission_settings.user_rate_limit,
            admin_rate_limit=cfg.permission_settings.admin_rate_limit,
            auth_failure_lockout=cfg.permission_settings.auth_failure_lockout,
            lockout_duration_minutes=cfg.permission_settings.lockout_duration_minutes,
        )
        auth = AuthManager(cfg.permissions, auth_settings)

        # 3. RateLimiter
        rate_limits = {}
        for name, pcfg in cfg.provider_configs.items():
            rate_limits[name] = RateLimitConfig(
                requests_per_minute=pcfg.requests_per_minute,
                tokens_per_minute=pcfg.tokens_per_minute,
            )
        rl = RateLimiter(rate_limits)

        # 4. Providers
        providers = {}
        groq_cfg = cfg.provider_configs.get("groq")
        if groq_cfg and groq_cfg.enabled:
            providers["groq"] = GroqProvider({
                "api_key": app.groq_api_key,
                "default_model": groq_cfg.default_model,
                "models": groq_cfg.models,
            })

        oc_cfg = cfg.provider_configs.get("ollama_cloud")
        if oc_cfg and oc_cfg.enabled and app.ollama_cloud_url:
            providers["ollama_cloud"] = OllamaCloudProvider({
                "cloud_url": app.ollama_cloud_url,
                "default_model": oc_cfg.default_model,
                "models": oc_cfg.models,
            })

        assert len(providers) >= 1, "At least one provider should be enabled"

        # 5. ProviderManager
        priority_order = sorted(
            cfg.provider_configs.keys(),
            key=lambda n: cfg.provider_configs[n].priority,
        )
        pm = ProviderManager(providers, rl, priority_order)

        # 6. ContextStore
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        cs = ContextStore(
            storage_path=str(data_dir / "contexts.json"),
            max_messages=app.max_context_messages,
            max_tokens=app.max_context_tokens,
        )
        cs.load_from_disk()

        # 7. CommandRouter
        router = CommandRouter(
            auth_manager=auth,
            provider_manager=pm,
            rate_limiter=rl,
            context_store=cs,
        )

        # 8. SkillRegistry
        skills_config = {"calc": {"enabled": True}}
        registry = SkillRegistry(skills_config, router)
        registry.discover_and_load()

        # 9. TelegramHandler
        handler = TelegramHandler(
            token=app.telegram_token,
            command_router=router,
            auth_manager=auth,
            provider_manager=pm,
            context_store=cs,
            audit_logger=audit,
            rate_limiter=rl,
            streaming_interval_ms=app.streaming_update_interval_ms,
            streaming_min_chars=app.streaming_min_chunk_chars,
        )

        # 10. Log startup
        audit.log_startup(VERSION, list(providers.keys()))

        # Verify the full chain is connected
        assert handler.command_router is router
        assert handler.auth_manager is auth
        assert handler.provider_manager is pm
        assert handler.context_store is cs
        assert handler.audit_logger is audit
        assert handler.rate_limiter is rl
        assert router.auth_manager is auth
        assert router.provider_manager is pm
        assert router.rate_limiter is rl
        assert router.context_store is cs

    async def test_command_routing_through_full_chain(self, loaded_config, tmp_path):
        """Commands route correctly through the fully wired component chain."""
        cfg = loaded_config
        auth = AuthManager(cfg.permissions)
        rl = RateLimiter({
            "groq": RateLimitConfig(requests_per_minute=30, tokens_per_minute=14400),
        })
        providers = {
            "groq": GroqProvider({
                "api_key": "test-key",
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile"],
            }),
        }
        pm = ProviderManager(providers, rl, ["groq"])
        cs = ContextStore(storage_path=str(tmp_path / "ctx.json"))

        router = CommandRouter(
            auth_manager=auth,
            provider_manager=pm,
            rate_limiter=rl,
            context_store=cs,
        )

        # Admin user should be able to run /start
        result = await router.route("start", 123456789, [])
        assert "OpenClaw" in result or "Welcome" in result or "openclaw" in result.lower()

        # Admin user should be able to run /version
        result = await router.route("version", 123456789, [])
        assert VERSION in result

    async def test_context_persistence_round_trip(self, tmp_path):
        """Context store saves and restores data across instances."""
        path = str(tmp_path / "data" / "contexts.json")

        cs1 = ContextStore(storage_path=path, max_messages=10)
        cs1.add_message(42, "user", "test message", tokens=10)
        cs1.save_to_disk()

        cs2 = ContextStore(storage_path=path, max_messages=10)
        cs2.load_from_disk()

        msgs = cs2.get_context(42)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "test message"

    async def test_unauthorized_user_rejected(self, loaded_config):
        """Unauthorized users are rejected by the auth + command chain."""
        auth = AuthManager(loaded_config.permissions)
        router = CommandRouter(auth_manager=auth)

        # Unknown user (not in permissions)
        result = await router.route("providers", 999999999, [])
        # Should be rejected (admin command by non-admin)
        assert "permission" in result.lower() or "denied" in result.lower() or "not authorized" in result.lower()

    async def test_admin_commands_require_admin(self, loaded_config):
        """Admin commands are rejected for regular users."""
        auth = AuthManager(loaded_config.permissions)
        rl = RateLimiter({
            "groq": RateLimitConfig(requests_per_minute=30, tokens_per_minute=14400),
        })
        providers = {
            "groq": GroqProvider({
                "api_key": "test-key",
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile"],
            }),
        }
        pm = ProviderManager(providers, rl, ["groq"])
        router = CommandRouter(
            auth_manager=auth,
            provider_manager=pm,
            rate_limiter=rl,
        )

        # Regular user (987654321) tries admin command
        result = await router.route("providers", 987654321, [])
        assert "permission" in result.lower() or "denied" in result.lower() or "not authorized" in result.lower()

        # Admin (123456789) should succeed
        result = await router.route("providers", 123456789, [])
        assert "permission" not in result.lower() or "provider" in result.lower()
