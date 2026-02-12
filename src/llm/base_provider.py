"""Base provider interface for LLM providers in OpenClaw Telegram Bot."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    
    content: str
    tokens_used: int
    model: str
    provider: str
    latency_ms: float
    finish_reason: str = "stop"
    error: Optional[str] = None


@dataclass
class ProviderStatus:
    """Health status of a provider."""
    
    name: str
    is_healthy: bool
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    latency_ms: Optional[float] = None


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: dict[str, Any]):
        """Initialize provider.
        
        Args:
            config: Provider configuration dictionary
        """
        self.config = config
        self.name: str = "base"
        self.is_healthy: bool = True
        self.last_error: Optional[str] = None
        self.error_count: int = 0
        self.last_check: Optional[datetime] = None
        self.last_latency_ms: Optional[float] = None
        self._default_model: str = ""
        self._available_models: list[str] = []
    
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Yields:
            Response content chunks as strings
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available.
        
        Returns:
            True if provider is healthy
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Return list of available models.
        
        Returns:
            List of model names
        """
        pass
    
    def get_default_model(self) -> str:
        """Get the default model for this provider.
        
        Returns:
            Default model name
        """
        return self._default_model

    @property
    def current_model(self) -> str:
        """Get the current active model for this provider.

        Returns:
            Current model name
        """
        return self._default_model

    def set_model(self, model_name: str) -> bool:
        """Set the active model for this provider.

        Args:
            model_name: Name of the model to activate

        Returns:
            True if model was set successfully, False if model not available
        """
        if model_name not in self._available_models:
            logger.warning(
                f"Provider {self.name}: model '{model_name}' not in available models"
            )
            return False
        self._default_model = model_name
        logger.info(f"Provider {self.name}: active model set to '{model_name}'")
        return True
    
    def mark_unhealthy(self, error: str) -> None:
        """Mark provider as unhealthy after failure.
        
        Args:
            error: Error message describing the failure
        """
        self.is_healthy = False
        self.last_error = error
        self.error_count += 1
        self.last_check = datetime.now()
        logger.warning(f"Provider {self.name} marked unhealthy: {error}")
    
    def mark_healthy(self) -> None:
        """Mark provider as healthy after successful request."""
        was_unhealthy = not self.is_healthy
        self.is_healthy = True
        self.last_error = None
        self.error_count = 0
        self.last_check = datetime.now()
        
        if was_unhealthy:
            logger.info(f"Provider {self.name} recovered and marked healthy")
    
    def get_status(self) -> ProviderStatus:
        """Get current provider status.
        
        Returns:
            ProviderStatus with current health info
        """
        return ProviderStatus(
            name=self.name,
            is_healthy=self.is_healthy,
            last_check=self.last_check,
            last_error=self.last_error,
            error_count=self.error_count,
            latency_ms=self.last_latency_ms,
        )
