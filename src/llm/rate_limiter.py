"""Rate limiting for LLM providers in OpenClaw Telegram Bot."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a provider."""
    
    requests_per_minute: int = 30
    tokens_per_minute: int = 14400


@dataclass
class UsageWindow:
    """Sliding window of usage data."""
    
    requests: list[datetime] = field(default_factory=list)
    tokens: list[tuple[datetime, int]] = field(default_factory=list)


class RateLimiter:
    """Manages API rate limits using sliding window algorithm."""
    
    def __init__(self, limits: dict[str, RateLimitConfig]):
        """Initialize RateLimiter.
        
        Args:
            limits: Dict mapping provider name to RateLimitConfig
        """
        self.limits = limits
        self.usage: dict[str, UsageWindow] = {}
        
        # Initialize usage windows for each provider
        for provider in limits:
            self.usage[provider] = UsageWindow()
    
    def _clean_window(self, provider: str) -> None:
        """Remove entries older than 1 minute from the sliding window.
        
        Args:
            provider: Provider name
        """
        if provider not in self.usage:
            return
        
        cutoff = datetime.now() - timedelta(minutes=1)
        window = self.usage[provider]
        
        window.requests = [t for t in window.requests if t > cutoff]
        window.tokens = [(t, n) for t, n in window.tokens if t > cutoff]
    
    def can_request(self, provider: str) -> bool:
        """Check if a request can be made without exceeding limits.
        
        Args:
            provider: Provider name
            
        Returns:
            True if request is allowed
        """
        if provider not in self.limits:
            return True  # No limits configured
        
        self._clean_window(provider)
        
        limit = self.limits[provider]
        window = self.usage.get(provider, UsageWindow())
        
        # Check request count
        if len(window.requests) >= limit.requests_per_minute:
            return False
        
        return True
    
    def can_request_tokens(self, provider: str, tokens: int) -> bool:
        """Check if a request with given tokens can be made.
        
        Args:
            provider: Provider name
            tokens: Estimated tokens for the request
            
        Returns:
            True if request is allowed
        """
        if provider not in self.limits:
            return True
        
        self._clean_window(provider)
        
        limit = self.limits[provider]
        window = self.usage.get(provider, UsageWindow())
        
        # Check request count
        if len(window.requests) >= limit.requests_per_minute:
            return False
        
        # Check token count
        current_tokens = sum(n for _, n in window.tokens)
        if current_tokens + tokens > limit.tokens_per_minute:
            return False
        
        return True
    
    def record_request(self, provider: str, tokens: int = 0) -> None:
        """Record a completed request.
        
        Args:
            provider: Provider name
            tokens: Tokens used in the request
        """
        if provider not in self.usage:
            self.usage[provider] = UsageWindow()
        
        now = datetime.now()
        self.usage[provider].requests.append(now)
        
        if tokens > 0:
            self.usage[provider].tokens.append((now, tokens))
        
        self._clean_window(provider)
    
    def get_usage_percentage(self, provider: str) -> dict[str, float]:
        """Get current usage as percentage of limits.
        
        Args:
            provider: Provider name
            
        Returns:
            Dict with 'rpm' and 'tpm' percentages (0.0 to 1.0+)
        """
        if provider not in self.limits:
            return {"rpm": 0.0, "tpm": 0.0}
        
        self._clean_window(provider)
        
        limit = self.limits[provider]
        window = self.usage.get(provider, UsageWindow())
        
        rpm_usage = len(window.requests) / limit.requests_per_minute if limit.requests_per_minute > 0 else 0.0
        
        current_tokens = sum(n for _, n in window.tokens)
        tpm_usage = current_tokens / limit.tokens_per_minute if limit.tokens_per_minute > 0 else 0.0
        
        return {"rpm": rpm_usage, "tpm": tpm_usage}
    
    def get_current_usage(self, provider: str) -> dict[str, int]:
        """Get current usage counts.
        
        Args:
            provider: Provider name
            
        Returns:
            Dict with 'requests' and 'tokens' counts
        """
        self._clean_window(provider)
        
        window = self.usage.get(provider, UsageWindow())
        
        return {
            "requests": len(window.requests),
            "tokens": sum(n for _, n in window.tokens),
        }
    
    def get_wait_time(self, provider: str) -> float:
        """Get seconds until rate limit resets.
        
        Args:
            provider: Provider name
            
        Returns:
            Seconds until oldest request expires from window
        """
        if provider not in self.usage:
            return 0.0
        
        window = self.usage[provider]
        
        if not window.requests:
            return 0.0
        
        oldest = min(window.requests)
        expires_at = oldest + timedelta(minutes=1)
        remaining = (expires_at - datetime.now()).total_seconds()
        
        return max(0.0, remaining)
    
    def should_failover(self, provider: str, threshold: float = 0.8) -> bool:
        """Check if usage is high enough to proactively failover.
        
        Args:
            provider: Provider name
            threshold: Usage percentage threshold (default 0.8 = 80%)
            
        Returns:
            True if either RPM or TPM exceeds threshold
        """
        usage = self.get_usage_percentage(provider)
        return usage["rpm"] >= threshold or usage["tpm"] >= threshold
    
    def get_all_usage(self) -> dict[str, dict[str, float]]:
        """Get usage percentages for all providers.
        
        Returns:
            Dict mapping provider name to usage percentages
        """
        return {
            provider: self.get_usage_percentage(provider)
            for provider in self.limits
        }
