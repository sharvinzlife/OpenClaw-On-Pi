"""Local Ollama LLM provider for OpenClaw Telegram Bot."""

import logging
import time
from typing import Any, AsyncIterator, Optional

import ollama
from ollama import ResponseError

from .base_provider import BaseProvider, LLMResponse

logger = logging.getLogger(__name__)


class LocalOllamaProvider(BaseProvider):
    """LLM provider using local Ollama instance."""

    DEFAULT_HOST = "http://localhost:11434"

    def __init__(self, config: dict[str, Any]):
        """Initialize Local Ollama provider.

        Args:
            config: Configuration with optional 'host' and 'default_model'
        """
        super().__init__(config)
        self.name = "ollama_local"
        self.host = config.get("host", self.DEFAULT_HOST)
        self.client = ollama.AsyncClient(host=self.host)
        self._default_model = config.get("default_model", "llama3.1")
        self._available_models = config.get("models", [])

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response using local Ollama.

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
        """Stream response chunks from local Ollama.

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
        """Check if local Ollama is available.

        Returns:
            True if provider is healthy
        """
        try:
            # List models to verify connectivity and discover available models
            response = await self.client.list()

            # Update available models from local instance
            if response and "models" in response:
                self._available_models = [
                    m.get("name", "").split(":")[0]  # Remove tag suffix
                    for m in response["models"]
                    if m.get("name")
                ]

            self.mark_healthy()
            return True
        except Exception as e:
            self.mark_unhealthy(f"Health check failed: {e}")
            return False

    def get_available_models(self) -> list[str]:
        """Return list of available local Ollama models.

        Note: This list is populated during health_check() from the local instance.

        Returns:
            List of model names
        """
        return self._available_models.copy()
