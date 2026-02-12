"""Command routing for OpenClaw Telegram Bot."""

from dataclasses import dataclass
from typing import Callable, Optional, Awaitable
import logging

from ..security.auth import AuthManager
from ..llm.provider_manager import ProviderManager
from ..llm.rate_limiter import RateLimiter
from ..utils.context_store import ContextStore

logger = logging.getLogger(__name__)

# Bot version
VERSION = "0.3.0"


@dataclass
class CommandHandler:
    """Registered command handler."""
    
    name: str
    handler: Callable[..., Awaitable[str]]
    permission_level: str
    description: str


class CommandRouter:
    """Routes Telegram commands to appropriate handlers."""
    
    def __init__(
        self,
        auth_manager: AuthManager,
        provider_manager: Optional[ProviderManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
        context_store: Optional[ContextStore] = None,
    ):
        """Initialize CommandRouter.
        
        Args:
            auth_manager: AuthManager for permission checks
            provider_manager: Optional ProviderManager for provider commands
            rate_limiter: Optional RateLimiter for quota commands
            context_store: Optional ContextStore for context commands
        """
        self.auth_manager = auth_manager
        self.provider_manager = provider_manager
        self.rate_limiter = rate_limiter
        self.context_store = context_store
        self.handlers: dict[str, CommandHandler] = {}
        
        # Register built-in commands
        self._register_core_commands()
        self._register_provider_commands()
        self._register_admin_commands()
    
    def register(
        self,
        command: str,
        handler: Callable[..., Awaitable[str]],
        permission_level: str = "guest",
        description: str = "",
    ) -> None:
        """Register a command handler.
        
        Args:
            command: Command name (without /)
            handler: Async function to handle command
            permission_level: Required permission level
            description: Command description for help
        """
        self.handlers[command] = CommandHandler(
            name=command,
            handler=handler,
            permission_level=permission_level,
            description=description,
        )
    
    async def route(
        self,
        command: str,
        user_id: int,
        args: list[str],
    ) -> str:
        """Route command to handler after permission check.
        
        Args:
            command: Command name (without /)
            user_id: Telegram user ID
            args: Command arguments
            
        Returns:
            Response string
        """
        # Check if command exists
        if command not in self.handlers:
            return f"Unknown command: /{command}. Use /help to see available commands."
        
        handler = self.handlers[command]
        
        # Check permission
        if not self.auth_manager.check_permission(user_id, handler.permission_level):
            logger.warning(f"User {user_id} denied access to /{command}")
            return "You don't have permission to use this command."
        
        # Execute handler
        try:
            return await handler.handler(user_id, args)
        except Exception as e:
            logger.error(f"Error executing /{command}: {e}")
            return f"Error executing command: {e}"
    
    def get_available_commands(self, user_id: int) -> list[CommandHandler]:
        """Get commands available to a user based on permissions.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of available CommandHandlers
        """
        available = []
        
        for handler in self.handlers.values():
            if self.auth_manager.check_permission(user_id, handler.permission_level):
                available.append(handler)
        
        return available
    
    def _register_core_commands(self) -> None:
        """Register core bot commands."""
        self.register("start", self.cmd_start, "guest", "Start the bot")
        self.register("help", self.cmd_help, "guest", "Show available commands")
        self.register("status", self.cmd_status, "guest", "Show bot status")
        self.register("settings", self.cmd_settings, "guest", "Show your settings")
        self.register("reset", self.cmd_reset, "user", "Clear conversation history")
        self.register("version", self.cmd_version, "guest", "Show bot version")
    
    def _register_provider_commands(self) -> None:
        """Register provider management commands."""
        self.register("provider", self.cmd_provider, "guest", "Show current provider")
        self.register("switch", self.cmd_switch, "guest", "Switch provider")
        self.register("models", self.cmd_models, "admin", "List available models")
        self.register("setmodel", self.cmd_setmodel, "admin", "Set preferred model")
        self.register("tokens", self.cmd_tokens, "guest", "Show token usage")
        self.register("quota", self.cmd_quota, "guest", "Show rate limit status")
    
    def _register_admin_commands(self) -> None:
        """Register admin-only commands."""
        self.register("providers", self.cmd_providers, "admin", "Show all provider status")
        self.register("costs", self.cmd_costs, "admin", "Show estimated costs")
        self.register("limits", self.cmd_limits, "admin", "Show rate limit details")
        self.register("reload", self.cmd_reload, "admin", "Reload configuration")
    
    # Core command handlers
    
    async def cmd_start(self, user_id: int, args: list[str]) -> str:
        """Handle /start command."""
        return (
            "👋 Welcome to OpenClaw AI Bot!\n\n"
            "I'm an AI assistant powered by multiple LLM providers. "
            "Just send me a message and I'll respond.\n\n"
            "Use /help to see available commands."
        )
    
    async def cmd_help(self, user_id: int, args: list[str]) -> str:
        """Handle /help command."""
        available = self.get_available_commands(user_id)
        
        lines = ["📚 Available Commands:\n"]
        for handler in sorted(available, key=lambda h: h.name):
            lines.append(f"/{handler.name} - {handler.description}")
        
        return "\n".join(lines)
    
    async def cmd_status(self, user_id: int, args: list[str]) -> str:
        """Handle /status command."""
        lines = ["📊 Bot Status:\n"]
        
        if self.provider_manager:
            status = self.provider_manager.get_all_status()
            healthy_count = sum(1 for s in status.values() if s.is_healthy)
            lines.append(f"Providers: {healthy_count}/{len(status)} healthy")
            
            for name, s in status.items():
                icon = "✅" if s.is_healthy else "❌"
                lines.append(f"  {icon} {name}")
        
        return "\n".join(lines)
    
    async def cmd_settings(self, user_id: int, args: list[str]) -> str:
        """Handle /settings command."""
        lines = ["⚙️ Your Settings:\n"]
        
        if self.provider_manager:
            pref = self.provider_manager.get_user_preference(user_id)
            lines.append(f"Preferred provider: {pref or 'default'}")
        
        if self.context_store:
            stats = self.context_store.get_context_stats(user_id)
            lines.append(f"Context messages: {stats['message_count']}")
        
        return "\n".join(lines)
    
    async def cmd_reset(self, user_id: int, args: list[str]) -> str:
        """Handle /reset command."""
        if self.context_store:
            self.context_store.clear_context(user_id)
            return "🔄 Conversation history cleared."
        return "Context store not available."
    
    async def cmd_version(self, user_id: int, args: list[str]) -> str:
        """Handle /version command."""
        return f"🤖 OpenClaw Bot v{VERSION}"
    
    # Provider command handlers
    
    async def cmd_provider(self, user_id: int, args: list[str]) -> str:
        """Handle /provider command."""
        if not self.provider_manager:
            return "Provider manager not available."
        
        provider = self.provider_manager.get_provider(user_id)
        if provider:
            return f"🔌 Current provider: {provider.name}"
        return "No provider available."
    
    async def cmd_switch(self, user_id: int, args: list[str]) -> str:
        """Handle /switch command."""
        if not self.provider_manager:
            return "Provider manager not available."
        
        if not args:
            available = self.provider_manager.get_available_providers()
            return f"Usage: /switch <provider>\nAvailable: {', '.join(available)}"
        
        provider_name = args[0].lower()
        if self.provider_manager.set_user_preference(user_id, provider_name):
            return f"✅ Switched to {provider_name}"
        return f"❌ Provider '{provider_name}' not available."
    
    async def cmd_models(self, user_id: int, args: list[str]) -> str:
        """Handle /models command."""
        if not self.provider_manager:
            return "Provider manager not available."
        
        provider = self.provider_manager.get_provider(user_id)
        if not provider:
            return "No provider available."
        
        models = provider.get_available_models()
        return f"📋 Models for {provider.name}:\n" + "\n".join(f"  • {m}" for m in models)
    
    async def cmd_setmodel(self, user_id: int, args: list[str]) -> str:
        """Handle /setmodel command."""
        if not args:
            return "Usage: /setmodel <model_name>"
        
        # Model preference would be stored per-user
        # For now, just acknowledge
        return f"Model preference noted: {args[0]}"
    
    async def cmd_tokens(self, user_id: int, args: list[str]) -> str:
        """Handle /tokens command."""
        if not self.context_store:
            return "Context store not available."
        
        stats = self.context_store.get_context_stats(user_id)
        return f"📈 Token usage:\nTotal: {stats['total_tokens']}"
    
    async def cmd_quota(self, user_id: int, args: list[str]) -> str:
        """Handle /quota command."""
        if not self.rate_limiter:
            return "Rate limiter not available."
        
        lines = ["📊 Rate Limit Status:\n"]
        usage = self.rate_limiter.get_all_usage()
        
        for provider, pct in usage.items():
            rpm_pct = pct["rpm"] * 100
            tpm_pct = pct["tpm"] * 100
            lines.append(f"{provider}: {rpm_pct:.1f}% RPM, {tpm_pct:.1f}% TPM")
        
        return "\n".join(lines)
    
    # Admin command handlers
    
    async def cmd_providers(self, user_id: int, args: list[str]) -> str:
        """Handle /providers command (admin)."""
        if not self.provider_manager:
            return "Provider manager not available."
        
        lines = ["🔧 Provider Details:\n"]
        status = self.provider_manager.get_all_status()
        
        for name, s in status.items():
            icon = "✅" if s.is_healthy else "❌"
            lines.append(f"{icon} {name}")
            if s.latency_ms:
                lines.append(f"   Latency: {s.latency_ms:.0f}ms")
            if s.error_count > 0:
                lines.append(f"   Errors: {s.error_count}")
            if s.last_error:
                lines.append(f"   Last error: {s.last_error[:50]}")
        
        return "\n".join(lines)
    
    async def cmd_costs(self, user_id: int, args: list[str]) -> str:
        """Handle /costs command (admin)."""
        # Cost tracking would require more detailed usage data
        return "💰 Cost tracking not yet implemented."
    
    async def cmd_limits(self, user_id: int, args: list[str]) -> str:
        """Handle /limits command (admin)."""
        if not self.rate_limiter:
            return "Rate limiter not available."
        
        lines = ["📉 Rate Limit Details:\n"]
        
        for provider, config in self.rate_limiter.limits.items():
            usage = self.rate_limiter.get_current_usage(provider)
            lines.append(f"{provider}:")
            lines.append(f"  RPM: {usage['requests']}/{config.requests_per_minute}")
            lines.append(f"  TPM: {usage['tokens']}/{config.tokens_per_minute}")
        
        return "\n".join(lines)
    
    async def cmd_reload(self, user_id: int, args: list[str]) -> str:
        """Handle /reload command (admin)."""
        # Would trigger config reload
        return "🔄 Configuration reload requested."
