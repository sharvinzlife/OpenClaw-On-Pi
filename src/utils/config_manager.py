"""Configuration management for OpenClaw Telegram Bot."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging
import os

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration loaded from all sources."""
    
    # Secrets from .env
    telegram_token: str = ""
    groq_api_key: str = ""
    ollama_cloud_url: Optional[str] = None
    ollama_api_key: Optional[str] = None
    
    # Bot settings from config.yaml
    default_provider: str = "groq"
    default_model: str = "llama-3.1-70b-versatile"
    response_timeout: int = 30
    max_context_messages: int = 10
    max_context_tokens: int = 4000
    
    # Logging settings
    log_level: str = "INFO"
    log_retention_days: int = 30
    audit_path: str = "logs/audit.log"
    
    # Streaming settings
    streaming_update_interval_ms: int = 500
    streaming_min_chunk_chars: int = 50


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    
    name: str
    enabled: bool = True
    priority: int = 1
    requests_per_minute: int = 30
    tokens_per_minute: int = 14400
    models: list[str] = field(default_factory=list)
    default_model: str = ""


@dataclass
class PermissionSettings:
    """Permission-related settings."""
    
    allow_unknown_users: bool = False
    guest_rate_limit: int = 5
    user_rate_limit: int = 20
    admin_rate_limit: int = 100
    auth_failure_lockout: int = 5
    lockout_duration_minutes: int = 15


class ConfigManager:
    """Loads and validates configuration from multiple sources."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.app_config: Optional[AppConfig] = None
        self.provider_configs: dict[str, ProviderConfig] = {}
        self.permissions: dict[int, str] = {}  # user_id -> level
        self.permission_settings: Optional[PermissionSettings] = None
        self._env_loaded = False
    
    def load_all(self) -> None:
        """Load all configuration files."""
        self.load_env()
        
        config_data = self.load_yaml("config.yaml")
        permissions_data = self.load_yaml("permissions.yaml")
        providers_data = self.load_yaml("providers.yaml")
        
        self._parse_app_config(config_data)
        self._parse_permissions(permissions_data)
        self._parse_providers(providers_data)
        
        logger.info("Configuration loaded successfully")
    
    def load_env(self) -> dict[str, str]:
        """Load secrets from .env file."""
        env_path = self.config_dir / ".env"
        
        if env_path.exists():
            load_dotenv(env_path)
            self._env_loaded = True
            logger.debug(f"Loaded environment from {env_path}")
        else:
            logger.warning(f"No .env file found at {env_path}")
        
        return {
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "OLLAMA_CLOUD_URL": os.getenv("OLLAMA_CLOUD_URL", ""),
        }
    
    def load_yaml(self, filename: str) -> dict[str, Any]:
        """Load YAML configuration file."""
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}")
            return {}
        
        with open(filepath, "r") as f:
            data = yaml.safe_load(f) or {}
        
        logger.debug(f"Loaded config from {filepath}")
        return data
    
    def validate(self) -> list[str]:
        """Validate configuration, return list of errors."""
        errors = []
        
        if not self.app_config:
            errors.append("Configuration not loaded")
            return errors
        
        # Required secrets
        if not self.app_config.telegram_token:
            errors.append("Missing required: TELEGRAM_BOT_TOKEN")
        
        if not self.app_config.groq_api_key:
            errors.append("Missing required: GROQ_API_KEY")
        
        # Validate at least one provider is enabled
        enabled_providers = [
            name for name, cfg in self.provider_configs.items() 
            if cfg.enabled
        ]
        if not enabled_providers:
            errors.append("No LLM providers enabled")
        
        # Validate default provider exists and is enabled
        if self.app_config.default_provider not in enabled_providers:
            errors.append(
                f"Default provider '{self.app_config.default_provider}' "
                "is not enabled"
            )
        
        return errors
    
    def reload_hot(self) -> None:
        """Reload non-critical settings without restart."""
        # Reload permissions (can change without restart)
        permissions_data = self.load_yaml("permissions.yaml")
        self._parse_permissions(permissions_data)
        
        # Reload provider configs (rate limits, models)
        providers_data = self.load_yaml("providers.yaml")
        self._parse_providers(providers_data)
        
        logger.info("Hot-reloaded configuration")
    
    def _parse_app_config(self, config_data: dict[str, Any]) -> None:
        """Parse application config from loaded data."""
        bot = config_data.get("bot", {})
        logging_cfg = config_data.get("logging", {})
        streaming = config_data.get("streaming", {})
        
        self.app_config = AppConfig(
            # Secrets from environment
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            ollama_cloud_url=os.getenv("OLLAMA_CLOUD_URL") or None,
            ollama_api_key=os.getenv("OLLAMA_API_KEY") or None,
            # Bot settings
            default_provider=bot.get("default_provider", "groq"),
            default_model=bot.get("default_model", "llama-3.1-70b-versatile"),
            response_timeout=bot.get("response_timeout", 30),
            max_context_messages=bot.get("max_context_messages", 10),
            max_context_tokens=bot.get("max_context_tokens", 4000),
            # Logging
            log_level=logging_cfg.get("level", "INFO"),
            log_retention_days=logging_cfg.get("retention_days", 30),
            audit_path=logging_cfg.get("audit_path", "logs/audit.log"),
            # Streaming
            streaming_update_interval_ms=streaming.get("update_interval_ms", 500),
            streaming_min_chunk_chars=streaming.get("min_chunk_chars", 50),
        )
    
    def _parse_permissions(self, data: dict[str, Any]) -> None:
        """Parse permissions from loaded data."""
        self.permissions = {}
        
        # Parse user lists by permission level
        for user_id in data.get("admins", []) or []:
            if user_id:
                self.permissions[int(user_id)] = "admin"
        
        for user_id in data.get("users", []) or []:
            if user_id:
                self.permissions[int(user_id)] = "user"
        
        for user_id in data.get("guests", []) or []:
            if user_id:
                self.permissions[int(user_id)] = "guest"
        
        # Parse settings
        settings = data.get("settings", {})
        self.permission_settings = PermissionSettings(
            allow_unknown_users=settings.get("allow_unknown_users", False),
            guest_rate_limit=settings.get("guest_rate_limit", 5),
            user_rate_limit=settings.get("user_rate_limit", 20),
            admin_rate_limit=settings.get("admin_rate_limit", 100),
            auth_failure_lockout=settings.get("auth_failure_lockout", 5),
            lockout_duration_minutes=settings.get("lockout_duration_minutes", 15),
        )
    
    def _parse_providers(self, data: dict[str, Any]) -> None:
        """Parse provider configs from loaded data."""
        self.provider_configs = {}
        
        for name, cfg in data.items():
            if not isinstance(cfg, dict):
                continue
            
            rate_limits = cfg.get("rate_limits", {})
            
            self.provider_configs[name] = ProviderConfig(
                name=name,
                enabled=cfg.get("enabled", True),
                priority=cfg.get("priority", 99),
                requests_per_minute=rate_limits.get("requests_per_minute", 30),
                tokens_per_minute=rate_limits.get("tokens_per_minute", 14400),
                models=cfg.get("models", []),
                default_model=cfg.get("default_model", ""),
            )
