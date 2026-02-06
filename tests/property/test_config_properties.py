"""Property-based tests for ConfigManager.

Feature: openclaw-telegram-bot
Tests Properties 1 and 2 from the design document.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings, strategies as st, HealthCheck

from src.utils.config_manager import ConfigManager, AppConfig


# Strategies for generating valid config data
valid_provider_name = st.sampled_from(["groq", "ollama_cloud", "ollama_local"])
valid_log_level = st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"])
positive_int = st.integers(min_value=1, max_value=10000)


@st.composite
def valid_bot_config(draw):
    """Generate valid bot configuration section."""
    return {
        "default_provider": draw(valid_provider_name),
        "default_model": draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip())),
        "response_timeout": draw(positive_int),
        "max_context_messages": draw(st.integers(min_value=1, max_value=100)),
        "max_context_tokens": draw(st.integers(min_value=100, max_value=100000)),
    }


@st.composite
def valid_logging_config(draw):
    """Generate valid logging configuration section."""
    return {
        "level": draw(valid_log_level),
        "retention_days": draw(st.integers(min_value=1, max_value=365)),
        "audit_path": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
    }


@st.composite
def valid_streaming_config(draw):
    """Generate valid streaming configuration section."""
    return {
        "update_interval_ms": draw(st.integers(min_value=100, max_value=5000)),
        "min_chunk_chars": draw(st.integers(min_value=10, max_value=500)),
    }


@st.composite
def valid_provider_config(draw, name: str):
    """Generate valid provider configuration."""
    return {
        "enabled": draw(st.booleans()),
        "priority": draw(st.integers(min_value=1, max_value=10)),
        "rate_limits": {
            "requests_per_minute": draw(positive_int),
            "tokens_per_minute": draw(st.integers(min_value=1000, max_value=1000000)),
        },
        "models": draw(st.lists(st.text(min_size=1, max_size=30).filter(lambda x: x.strip()), min_size=1, max_size=5)),
        "default_model": draw(st.text(min_size=1, max_size=30).filter(lambda x: x.strip())),
    }


@st.composite
def valid_full_config(draw):
    """Generate a complete valid configuration set."""
    bot = draw(valid_bot_config())
    logging_cfg = draw(valid_logging_config())
    streaming = draw(valid_streaming_config())
    
    # Ensure at least one provider is enabled and matches default
    providers = {}
    for name in ["groq", "ollama_cloud", "ollama_local"]:
        providers[name] = draw(valid_provider_config(name))
    
    # Force the default provider to be enabled
    providers[bot["default_provider"]]["enabled"] = True
    
    # Generate env values without trailing/leading whitespace (dotenv strips these)
    return {
        "config": {"bot": bot, "logging": logging_cfg, "streaming": streaming},
        "providers": providers,
        "env": {
            "TELEGRAM_BOT_TOKEN": draw(st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N')))),
            "GROQ_API_KEY": draw(st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N')))),
            "OLLAMA_CLOUD_URL": draw(st.text(min_size=0, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P')))),
        }
    }


class TestConfigLoadingCompleteness:
    """Property 1: Configuration Loading Completeness
    
    For any valid set of configuration files (.env, config.yaml, permissions.yaml, 
    providers.yaml), loading them through ConfigManager SHALL populate all required 
    fields in AppConfig without errors.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """
    
    @given(full_config=valid_full_config())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_config_loads_completely(self, full_config):
        """Property 1: Valid configs load all required AppConfig fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Write config.yaml
            with open(config_dir / "config.yaml", "w") as f:
                yaml.dump(full_config["config"], f)
            
            # Write providers.yaml
            with open(config_dir / "providers.yaml", "w") as f:
                yaml.dump(full_config["providers"], f)
            
            # Write permissions.yaml (minimal valid)
            with open(config_dir / "permissions.yaml", "w") as f:
                yaml.dump({"admins": [], "users": [], "guests": [], "settings": {}}, f)
            
            # Write .env
            with open(config_dir / ".env", "w") as f:
                for key, value in full_config["env"].items():
                    f.write(f"{key}={value}\n")
            
            # Clear any existing env vars to avoid interference
            for key in ["TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"]:
                os.environ.pop(key, None)
            
            # Load configuration
            manager = ConfigManager(str(config_dir))
            manager.load_all()
            
            # Verify AppConfig is populated
            assert manager.app_config is not None
            
            # Verify all required fields are populated from config
            bot_cfg = full_config["config"]["bot"]
            assert manager.app_config.default_provider == bot_cfg["default_provider"]
            assert manager.app_config.default_model == bot_cfg["default_model"]
            assert manager.app_config.response_timeout == bot_cfg["response_timeout"]
            assert manager.app_config.max_context_messages == bot_cfg["max_context_messages"]
            assert manager.app_config.max_context_tokens == bot_cfg["max_context_tokens"]
            
            # Verify logging config
            log_cfg = full_config["config"]["logging"]
            assert manager.app_config.log_level == log_cfg["level"]
            assert manager.app_config.log_retention_days == log_cfg["retention_days"]
            
            # Verify streaming config
            stream_cfg = full_config["config"]["streaming"]
            assert manager.app_config.streaming_update_interval_ms == stream_cfg["update_interval_ms"]
            assert manager.app_config.streaming_min_chunk_chars == stream_cfg["min_chunk_chars"]
            
            # Verify secrets loaded from env
            assert manager.app_config.telegram_token == full_config["env"]["TELEGRAM_BOT_TOKEN"]
            assert manager.app_config.groq_api_key == full_config["env"]["GROQ_API_KEY"]
            
            # Verify providers loaded
            for name in full_config["providers"]:
                assert name in manager.provider_configs


class TestConfigValidationRejectsIncomplete:
    """Property 2: Configuration Validation Rejects Incomplete Configs
    
    For any configuration file set missing a required field (TELEGRAM_BOT_TOKEN, 
    GROQ_API_KEY), the ConfigManager.validate() SHALL return a non-empty error list.
    
    **Validates: Requirements 2.5**
    """
    
    @given(
        has_telegram_token=st.booleans(),
        has_groq_key=st.booleans(),
    )
    @settings(max_examples=100)
    def test_missing_required_fields_rejected(self, has_telegram_token, has_groq_key):
        """Property 2: Missing required fields produce validation errors."""
        # Skip the case where both are present (that's valid)
        if has_telegram_token and has_groq_key:
            return
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Write minimal config.yaml
            with open(config_dir / "config.yaml", "w") as f:
                yaml.dump({
                    "bot": {"default_provider": "groq"},
                    "logging": {},
                    "streaming": {}
                }, f)
            
            # Write providers.yaml with groq enabled
            with open(config_dir / "providers.yaml", "w") as f:
                yaml.dump({
                    "groq": {"enabled": True, "priority": 1, "rate_limits": {}}
                }, f)
            
            # Write permissions.yaml
            with open(config_dir / "permissions.yaml", "w") as f:
                yaml.dump({"admins": [], "users": [], "guests": [], "settings": {}}, f)
            
            # Write .env with conditional secrets
            env_content = []
            if has_telegram_token:
                env_content.append("TELEGRAM_BOT_TOKEN=test_token_123")
            if has_groq_key:
                env_content.append("GROQ_API_KEY=test_key_456")
            
            with open(config_dir / ".env", "w") as f:
                f.write("\n".join(env_content))
            
            # Clear env vars
            for key in ["TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"]:
                os.environ.pop(key, None)
            
            # Load and validate
            manager = ConfigManager(str(config_dir))
            manager.load_all()
            errors = manager.validate()
            
            # Should have errors for missing required fields
            assert len(errors) > 0, "Expected validation errors for missing required fields"
            
            if not has_telegram_token:
                assert any("TELEGRAM_BOT_TOKEN" in e for e in errors)
            if not has_groq_key:
                assert any("GROQ_API_KEY" in e for e in errors)
    
    @given(st.data())
    @settings(max_examples=50)
    def test_no_enabled_providers_rejected(self, data):
        """Validation rejects config with no enabled providers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Write config.yaml
            with open(config_dir / "config.yaml", "w") as f:
                yaml.dump({
                    "bot": {"default_provider": "groq"},
                    "logging": {},
                    "streaming": {}
                }, f)
            
            # Write providers.yaml with ALL providers disabled
            with open(config_dir / "providers.yaml", "w") as f:
                yaml.dump({
                    "groq": {"enabled": False, "priority": 1},
                    "ollama_cloud": {"enabled": False, "priority": 2},
                    "ollama_local": {"enabled": False, "priority": 3},
                }, f)
            
            # Write permissions.yaml
            with open(config_dir / "permissions.yaml", "w") as f:
                yaml.dump({"admins": [], "users": [], "guests": [], "settings": {}}, f)
            
            # Write .env with valid secrets
            with open(config_dir / ".env", "w") as f:
                f.write("TELEGRAM_BOT_TOKEN=test_token\n")
                f.write("GROQ_API_KEY=test_key\n")
            
            # Clear env vars
            for key in ["TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "OLLAMA_CLOUD_URL"]:
                os.environ.pop(key, None)
            
            manager = ConfigManager(str(config_dir))
            manager.load_all()
            errors = manager.validate()
            
            # Should have error about no providers enabled
            assert len(errors) > 0
            assert any("provider" in e.lower() for e in errors)
