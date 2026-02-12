"""Main entry point for OpenClaw Telegram Bot."""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

from .utils.config_manager import ConfigManager
from .utils.audit_logger import AuditLogger
from .utils.context_store import ContextStore
from .security.auth import AuthManager, AuthSettings
from .llm.rate_limiter import RateLimiter, RateLimitConfig
from .llm.groq_provider import GroqProvider
from .llm.ollama_cloud_provider import OllamaCloudProvider
from .llm.ollama_local_provider import LocalOllamaProvider
from .llm.provider_manager import ProviderManager
from .bot.command_router import CommandRouter, VERSION
from .bot.telegram_handler import TelegramHandler
from .skills.registry import SkillRegistry
from .web.dashboard import start_dashboard_thread, DashboardState, dashboard_state

logger = logging.getLogger(__name__)

# Global reference for signal handlers
_handler: TelegramHandler = None
_shutdown_event: asyncio.Event = None


async def main() -> None:
    """Initialize and run the bot."""
    global _handler, _shutdown_event
    
    # Determine config directory
    config_dir = Path("config")
    if not config_dir.exists():
        config_dir = Path(__file__).parent.parent / "config"
    
    # Load configuration
    logger.info("Loading configuration...")
    config_manager = ConfigManager(str(config_dir))
    config_manager.load_all()
    
    # Validate configuration
    errors = config_manager.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        sys.exit(1)
    
    app_config = config_manager.app_config
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, app_config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize audit logger
    audit_logger = AuditLogger(
        log_path=app_config.audit_path,
        retention_days=app_config.log_retention_days,
    )
    
    # Initialize auth manager
    auth_settings = AuthSettings(
        allow_unknown_users=config_manager.permission_settings.allow_unknown_users,
        guest_rate_limit=config_manager.permission_settings.guest_rate_limit,
        user_rate_limit=config_manager.permission_settings.user_rate_limit,
        admin_rate_limit=config_manager.permission_settings.admin_rate_limit,
        auth_failure_lockout=config_manager.permission_settings.auth_failure_lockout,
        lockout_duration_minutes=config_manager.permission_settings.lockout_duration_minutes,
    )
    auth_manager = AuthManager(config_manager.permissions, auth_settings)
    
    # Initialize rate limiter
    rate_limits = {}
    for name, cfg in config_manager.provider_configs.items():
        rate_limits[name] = RateLimitConfig(
            requests_per_minute=cfg.requests_per_minute,
            tokens_per_minute=cfg.tokens_per_minute,
        )
    rate_limiter = RateLimiter(rate_limits)
    
    # Initialize providers
    providers = {}
    
    groq_cfg = config_manager.provider_configs.get("groq")
    if groq_cfg and groq_cfg.enabled:
        providers["groq"] = GroqProvider({
            "api_key": app_config.groq_api_key,
            "default_model": groq_cfg.default_model,
            "models": groq_cfg.models,
        })
        logger.info("Groq provider initialized")
    
    ollama_cloud_cfg = config_manager.provider_configs.get("ollama_cloud")
    if ollama_cloud_cfg and ollama_cloud_cfg.enabled and app_config.ollama_cloud_url and app_config.ollama_api_key:
        providers["ollama_cloud"] = OllamaCloudProvider({
            "cloud_url": app_config.ollama_cloud_url,
            "api_key": app_config.ollama_api_key or "",
            "default_model": ollama_cloud_cfg.default_model,
            "models": ollama_cloud_cfg.models,
        })
        logger.info("Ollama Cloud provider initialized")
    
    ollama_local_cfg = config_manager.provider_configs.get("ollama_local")
    if ollama_local_cfg and ollama_local_cfg.enabled:
        providers["ollama_local"] = LocalOllamaProvider({
            "default_model": ollama_local_cfg.default_model,
            "models": ollama_local_cfg.models,
        })
        logger.info("Local Ollama provider initialized")
    
    if not providers:
        logger.error("No providers available")
        sys.exit(1)
    
    # Initialize provider manager
    priority_order = sorted(
        config_manager.provider_configs.keys(),
        key=lambda n: config_manager.provider_configs[n].priority
    )
    provider_manager = ProviderManager(providers, rate_limiter, priority_order)
    
    # Initialize context store
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    context_store = ContextStore(
        storage_path=str(data_dir / "contexts.json"),
        max_messages=app_config.max_context_messages,
        max_tokens=app_config.max_context_tokens,
    )
    context_store.load_from_disk()
    
    # Initialize command router
    command_router = CommandRouter(
        auth_manager=auth_manager,
        provider_manager=provider_manager,
        rate_limiter=rate_limiter,
        context_store=context_store,
    )
    
    # Load skills configuration and initialize skill registry
    skills_config_data = config_manager.load_yaml("skills.yaml")
    skills_config = skills_config_data.get("skills", {})
    skill_registry = SkillRegistry(skills_config, command_router)
    skill_registry.discover_and_load()
    loaded_count = len(skill_registry.skills)
    logger.info(f"Loaded {loaded_count} skill(s)")
    
    # Initialize Telegram handler
    _handler = TelegramHandler(
        token=app_config.telegram_token,
        command_router=command_router,
        auth_manager=auth_manager,
        provider_manager=provider_manager,
        context_store=context_store,
        audit_logger=audit_logger,
        rate_limiter=rate_limiter,
        streaming_interval_ms=app_config.streaming_update_interval_ms,
        streaming_min_chars=app_config.streaming_min_chunk_chars,
        skill_registry=skill_registry,
    )
    
    # Log startup
    audit_logger.log_startup(VERSION, list(providers.keys()))
    logger.info(f"OpenClaw Bot v{VERSION} starting...")
    
    # Initialize and start dashboard
    dashboard_state.bot_started = datetime.now()
    dashboard_state.bot_running = True
    dashboard_state.providers = {
        name: {"status": "ready", "healthy": provider.is_healthy}
        for name, provider in providers.items()
    }
    dashboard_state._providers_ref = providers
    
    # Set rate limits info for dashboard
    dashboard_state.rate_limits = {
        "Groq RPM": {"current": 0, "limit": 30},
        "Groq TPM": {"current": 0, "limit": 14400},
    }
    
    # Connect skill stats to dashboard state
    dashboard_state.skill_registry = skill_registry
    
    dashboard_port = getattr(app_config, 'dashboard_port', 8080)
    start_dashboard_thread(host='0.0.0.0', port=dashboard_port, state=dashboard_state, provider_manager=provider_manager)
    logger.info(f"Dashboard started at http://0.0.0.0:{dashboard_port}")
    
    # Setup shutdown event
    _shutdown_event = asyncio.Event()
    
    # Start bot
    await _handler.start()
    
    # Wait for shutdown signal
    await _shutdown_event.wait()
    
    # Graceful shutdown
    logger.info("Shutting down...")
    dashboard_state.bot_running = False
    await _handler.stop()
    audit_logger.log_shutdown("normal")
    logger.info("Shutdown complete")


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    if _shutdown_event:
        _shutdown_event.set()


def run():
    """Entry point for running the bot."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
