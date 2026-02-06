"""Groq LLM provider for OpenClaw Telegram Bot."""

import time
from typing import Any, AsyncIterator, Optional
import logging

from groq import AsyncGroq, APIError, APIConnectionError, RateLimitError

from .base_provider import BaseProvider, LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """LLM provider using Groq API."""
    
    DEFAULT_MODELS = [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    
    def __init__(self, config: dict[str, Any]):
        """Initialize Groq provider.
        
        Args:
            config: Configuration with 'api_key' and optional 'default_model'
        """
        super().__init__(config)
        self.name = "groq"
        self.client = AsyncGroq(api_key=config.get("api_key", ""))
        self._default_model = config.get("default_model", "openai/gpt-oss-120b")
        self._available_models = config.get("models", self.DEFAULT_MODELS)
    
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response using Groq.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Returns:
            LLMResponse with generated content
        """
        model = model or self._default_model
        start_time = time.time()
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            self.last_latency_ms = latency_ms
            self.mark_healthy()
            
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=model,
                provider=self.name,
                latency_ms=latency_ms,
                finish_reason=response.choices[0].finish_reason or "stop",
            )
            
        except RateLimitError as e:
            self.mark_unhealthy(f"Rate limit exceeded: {e}")
            raise
        except APIConnectionError as e:
            self.mark_unhealthy(f"Connection error: {e}")
            raise
        except APIError as e:
            self.mark_unhealthy(f"API error: {e}")
            raise
        except Exception as e:
            self.mark_unhealthy(f"Unexpected error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks from Groq.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Yields:
            Response content chunks as strings
        """
        model = model or self._default_model
        start_time = time.time()
        
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            latency_ms = (time.time() - start_time) * 1000
            self.last_latency_ms = latency_ms
            self.mark_healthy()
            
        except RateLimitError as e:
            self.mark_unhealthy(f"Rate limit exceeded: {e}")
            raise
        except APIConnectionError as e:
            self.mark_unhealthy(f"Connection error: {e}")
            raise
        except APIError as e:
            self.mark_unhealthy(f"API error: {e}")
            raise
        except Exception as e:
            self.mark_unhealthy(f"Unexpected error: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if Groq API is available.
        
        Returns:
            True if provider is healthy
        """
        try:
            # Simple API call to verify connectivity
            response = await self.client.chat.completions.create(
                model=self._default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            self.mark_healthy()
            return True
        except Exception as e:
            self.mark_unhealthy(f"Health check failed: {e}")
            return False
    
    def get_available_models(self) -> list[str]:
        """Return list of available Groq models.
        
        Returns:
            List of model names
        """
        return self._available_models.copy()
