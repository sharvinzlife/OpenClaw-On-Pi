"""Provider management with failover for OpenClaw Telegram Bot."""

import logging
from typing import Any, AsyncIterator, Optional

from .base_provider import BaseProvider, LLMResponse, ProviderStatus
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Error from a provider that should trigger failover."""

    pass


class AllProvidersFailedError(Exception):
    """All providers have failed."""

    pass


class ProviderManager:
    """Orchestrates provider selection, failover, and health monitoring."""

    DEFAULT_PRIORITY = ["groq", "ollama_cloud", "ollama_local"]

    def __init__(
        self,
        providers: dict[str, BaseProvider],
        rate_limiter: RateLimiter,
        priority_order: Optional[list[str]] = None,
    ):
        """Initialize ProviderManager.

        Args:
            providers: Dict mapping provider name to BaseProvider instance
            rate_limiter: RateLimiter instance for managing API limits
            priority_order: List of provider names in priority order
        """
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.priority_order = priority_order or self.DEFAULT_PRIORITY
        self.user_preferences: dict[int, str] = {}  # user_id -> preferred provider

    def get_provider(self, user_id: Optional[int] = None) -> Optional[BaseProvider]:
        """Get best available provider for user.

        Considers user preferences, provider health, and rate limits.

        Args:
            user_id: Optional user ID for preference lookup

        Returns:
            Best available provider, or None if all unavailable
        """
        # Check user preference first
        if user_id and user_id in self.user_preferences:
            preferred = self.user_preferences[user_id]
            if preferred in self.providers:
                provider = self.providers[preferred]
                if provider.is_healthy and not self.rate_limiter.should_failover(preferred):
                    return provider

        # Fall back to priority order
        for name in self.priority_order:
            if name not in self.providers:
                continue

            provider = self.providers[name]

            # Skip unhealthy providers
            if not provider.is_healthy:
                continue

            # Skip providers approaching rate limits
            if self.rate_limiter.should_failover(name):
                logger.debug(f"Skipping {name} due to rate limit threshold")
                continue

            return provider

        # Last resort: return any healthy provider
        for name, provider in self.providers.items():
            if provider.is_healthy:
                return provider

        return None

    async def generate_with_failover(
        self,
        messages: list[dict[str, str]],
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate response with automatic failover on failure.

        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: Optional user ID for preference lookup
            model: Optional model override

        Returns:
            LLMResponse from successful provider

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        tried_providers: list[str] = []
        last_error: Optional[Exception] = None

        for name in self._get_provider_order(user_id):
            if name in tried_providers:
                continue

            provider = self.providers.get(name)
            if not provider:
                continue

            # Skip unhealthy providers unless we've tried everything
            if not provider.is_healthy and len(tried_providers) < len(self.providers) - 1:
                continue

            tried_providers.append(name)

            try:
                # Check rate limits
                if not self.rate_limiter.can_request(name):
                    logger.debug(f"Skipping {name} due to rate limit")
                    continue

                response = await provider.generate(messages, model)

                # Record usage
                self.rate_limiter.record_request(name, response.tokens_used)

                # Log failover if we're not on the first choice
                if len(tried_providers) > 1:
                    logger.info(f"Failover successful: using {name}")

                return response

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {name} failed: {e}")
                provider.mark_unhealthy(str(e))
                continue

        raise AllProvidersFailedError(f"All providers failed. Last error: {last_error}")

    async def stream_with_failover(
        self,
        messages: list[dict[str, str]],
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response with automatic failover on failure.

        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: Optional user ID for preference lookup
            model: Optional model override

        Yields:
            Response content chunks

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        tried_providers: list[str] = []
        last_error: Optional[Exception] = None

        for name in self._get_provider_order(user_id):
            if name in tried_providers:
                continue

            provider = self.providers.get(name)
            if not provider:
                continue

            if not provider.is_healthy and len(tried_providers) < len(self.providers) - 1:
                continue

            tried_providers.append(name)

            try:
                if not self.rate_limiter.can_request(name):
                    continue

                # Record request (we don't know tokens for streaming)
                self.rate_limiter.record_request(name, tokens=0)
                logger.debug(
                    f"Streaming via provider '{name}', model param='{model}', provider default='{provider._default_model}'"
                )

                async for chunk in provider.stream(messages, model):
                    yield chunk

                # Success - exit the loop
                return

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {name} failed during streaming: {e}")
                provider.mark_unhealthy(str(e))
                continue

        raise AllProvidersFailedError(f"All providers failed. Last error: {last_error}")

    def _get_provider_order(self, user_id: Optional[int] = None) -> list[str]:
        """Get provider order considering user preference.

        Args:
            user_id: Optional user ID for preference lookup

        Returns:
            List of provider names in order to try
        """
        order = list(self.priority_order)

        # Move user's preferred provider to front
        if user_id and user_id in self.user_preferences:
            preferred = self.user_preferences[user_id]
            if preferred in order:
                order.remove(preferred)
                order.insert(0, preferred)

        return order

    def set_active_provider(self, provider_name: str) -> bool:
        """Set the globally active provider (moves it to front of priority).

        Args:
            provider_name: Name of the provider to make active

        Returns:
            True if set successfully
        """
        if provider_name not in self.providers:
            return False
        # Move to front of priority order
        if provider_name in self.priority_order:
            self.priority_order.remove(provider_name)
        self.priority_order.insert(0, provider_name)
        logger.info(f"Active provider set to {provider_name}")
        return True

    def get_active_provider(self) -> str:
        """Get the currently active (highest priority) provider name."""
        for name in self.priority_order:
            if name in self.providers:
                return name
        return list(self.providers.keys())[0] if self.providers else ""

    def set_user_preference(self, user_id: int, provider_name: str) -> bool:
        """Set user's preferred provider.

        Args:
            user_id: Telegram user ID
            provider_name: Name of preferred provider

        Returns:
            True if preference was set successfully
        """
        if provider_name not in self.providers:
            return False

        self.user_preferences[user_id] = provider_name
        logger.info(f"User {user_id} preference set to {provider_name}")
        return True

    def get_user_preference(self, user_id: int) -> Optional[str]:
        """Get user's preferred provider.

        Args:
            user_id: Telegram user ID

        Returns:
            Provider name or None
        """
        return self.user_preferences.get(user_id)

    def clear_user_preference(self, user_id: int) -> None:
        """Clear user's provider preference.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self.user_preferences:
            del self.user_preferences[user_id]

    def get_all_status(self) -> dict[str, ProviderStatus]:
        """Get health status of all providers.

        Returns:
            Dict mapping provider name to ProviderStatus
        """
        return {name: provider.get_status() for name, provider in self.providers.items()}

    async def run_health_checks(self) -> dict[str, bool]:
        """Run health checks on all providers.

        Returns:
            Dict mapping provider name to health status
        """
        results = {}

        for name, provider in self.providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False

        return results

    def get_available_providers(self) -> list[str]:
        """Get list of healthy provider names.

        Returns:
            List of healthy provider names
        """
        return [name for name, provider in self.providers.items() if provider.is_healthy]

    def get_all_models(self) -> dict[str, dict[str, Any]]:
        """Get all providers with their available models, current model, and active flag."""
        active = self.get_active_provider()
        result: dict[str, dict[str, Any]] = {}
        for name, provider in self.providers.items():
            result[name] = {
                "models": provider.get_available_models(),
                "current": provider.current_model,
                "active": name == active,
            }
        return result

    def set_provider_model(self, provider_name: str, model_name: str) -> bool:
        """Set the active model for a specific provider.

        Args:
            provider_name: Name of the provider
            model_name: Name of the model to activate

        Returns:
            True if model was set successfully, False if provider not found or model invalid
        """
        provider = self.providers.get(provider_name)
        if provider is None:
            return False
        return provider.set_model(model_name)
