"""Ollama Cloud LLM provider for OpenClaw Telegram Bot."""

import time
from typing import Any, AsyncIterator, Optional
import logging

import ollama
from ollama import ResponseError

from .base_provider import BaseProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaCloudProvider(BaseProvider):
    """LLM provider using remote Ollama instance."""
    
    DEFAULT_MODELS = [
        "llama3.1",
        "mistral",
    ]
    
    def __init__(self, config: dict[str, Any]):
        """Initialize Ollama Cloud provider.
        
        Args:
            config: Configuration with 'cloud_url' and optional 'default_model'
        """
        super().__init__(config)
        self.name = "ollama_cloud"
        self.cloud_url = config.get("cloud_url", "")
        self.client = ollama.AsyncClient(host=self.cloud_url)
        self._default_model = config.get("default_model", "llama3.1")
        self._available_models = config.get("models", self.DEFAULT_MODELS)
    
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response using Ollama Cloud.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Returns:
            LLMResponse with generated content
        """
        model = model or self._default_model
        start_time = time.time()
        
        try:
            response = await self.client.chat(
                model=model,
                messages=messages,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            self.last_latency_ms = latency_ms
            self.mark_healthy()
            
            content = response.get("message", {}).get("content", "")
            # Ollama doesn't always provide token counts
            tokens_used = response.get("eval_count", 0) + response.get("prompt_eval_count", 0)
            
            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=model,
                provider=self.name,
                latency_ms=latency_ms,
            )
            
        except ResponseError as e:
            self.mark_unhealthy(f"Ollama error: {e}")
            raise
        except Exception as e:
            self.mark_unhealthy(f"Unexpected error: {e}")
            raise
    
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response chunks from Ollama Cloud.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            
        Yields:
            Response content chunks as strings
        """
        model = model or self._default_model
        start_time = time.time()
        
        try:
            stream = await self.client.chat(
                model=model,
                messages=messages,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.get("message", {}).get("content"):
                    yield chunk["message"]["content"]
            
            latency_ms = (time.time() - start_time) * 1000
            self.last_latency_ms = latency_ms
            self.mark_healthy()
            
        except ResponseError as e:
            self.mark_unhealthy(f"Ollama error: {e}")
            raise
        except Exception as e:
            self.mark_unhealthy(f"Unexpected error: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if Ollama Cloud is available.
        
        Returns:
            True if provider is healthy
        """
        try:
            # List models to verify connectivity
            await self.client.list()
            self.mark_healthy()
            return True
        except Exception as e:
            self.mark_unhealthy(f"Health check failed: {e}")
            return False
    
    def get_available_models(self) -> list[str]:
        """Return list of available Ollama Cloud models.
        
        Returns:
            List of model names
        """
        return self._available_models.copy()
