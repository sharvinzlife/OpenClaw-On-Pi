"""Property-based tests for ProviderManager.

Feature: openclaw-telegram-bot
Tests Properties 3, 4, 5, and 11 from the design document.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from hypothesis import given, settings, strategies as st

from src.llm.base_provider import BaseProvider, LLMResponse
from src.llm.provider_manager import ProviderManager
from src.llm.rate_limiter import RateLimiter, RateLimitConfig


# Strategies
user_id_strategy = st.integers(min_value=1, max_value=10**12)
provider_name = st.sampled_from(["groq", "ollama_cloud", "ollama_local"])


def create_mock_provider(name: str, is_healthy: bool = True) -> MagicMock:
    """Create a mock provider for testing."""
    provider = MagicMock(spec=BaseProvider)
    provider.name = name
    provider.is_healthy = is_healthy
    provider.generate = AsyncMock(return_value=LLMResponse(
        content="test response",
        tokens_used=100,
        model="test-model",
        provider=name,
        latency_ms=50.0,
    ))
    provider.get_status = MagicMock(return_value=MagicMock(
        name=name,
        is_healthy=is_healthy,
    ))
    return provider


def create_rate_limiter() -> RateLimiter:
    """Create a rate limiter with high limits for testing."""
    return RateLimiter({
        "groq": RateLimitConfig(requests_per_minute=1000, tokens_per_minute=1000000),
        "ollama_cloud": RateLimitConfig(requests_per_minute=1000, tokens_per_minute=1000000),
        "ollama_local": RateLimitConfig(requests_per_minute=1000, tokens_per_minute=1000000),
    })


class TestProviderRoutingByPriority:
    """Property 3: Provider Routing by Priority
    
    For any set of provider health states, ProviderManager.get_provider() 
    SHALL return the highest-priority healthy provider according to the 
    priority order (groq > ollama_cloud > ollama_local).
    
    **Validates: Requirements 3.2**
    """
    
    @given(
        groq_healthy=st.booleans(),
        ollama_cloud_healthy=st.booleans(),
        ollama_local_healthy=st.booleans(),
    )
    @settings(max_examples=100, deadline=None)
    def test_returns_highest_priority_healthy_provider(
        self, groq_healthy, ollama_cloud_healthy, ollama_local_healthy
    ):
        """Property 3: Returns highest-priority healthy provider."""
        providers = {
            "groq": create_mock_provider("groq", groq_healthy),
            "ollama_cloud": create_mock_provider("ollama_cloud", ollama_cloud_healthy),
            "ollama_local": create_mock_provider("ollama_local", ollama_local_healthy),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=["groq", "ollama_cloud", "ollama_local"],
        )
        
        result = manager.get_provider()
        
        # Determine expected provider based on priority
        if groq_healthy:
            expected = "groq"
        elif ollama_cloud_healthy:
            expected = "ollama_cloud"
        elif ollama_local_healthy:
            expected = "ollama_local"
        else:
            expected = None
        
        if expected:
            assert result is not None
            assert result.name == expected, (
                f"Expected {expected}, got {result.name}. "
                f"Health: groq={groq_healthy}, cloud={ollama_cloud_healthy}, local={ollama_local_healthy}"
            )
        else:
            assert result is None
    
    @given(st.data())
    @settings(max_examples=50, deadline=None)
    def test_priority_order_respected(self, data):
        """Provider priority order is always respected."""
        # Generate random priority order
        priority = data.draw(st.permutations(["groq", "ollama_cloud", "ollama_local"]))
        
        # All providers healthy
        providers = {
            "groq": create_mock_provider("groq", True),
            "ollama_cloud": create_mock_provider("ollama_cloud", True),
            "ollama_local": create_mock_provider("ollama_local", True),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=list(priority),
        )
        
        result = manager.get_provider()
        
        # Should return first in priority order
        assert result is not None
        assert result.name == priority[0]


class TestProviderFailoverOnError:
    """Property 4: Provider Failover on Error
    
    For any provider that returns an error during generate_with_failover(), 
    the ProviderManager SHALL attempt the next provider in the failover chain 
    and eventually return a response if any provider succeeds.
    
    **Validates: Requirements 3.3**
    """
    
    @given(
        failing_providers=st.lists(
            st.sampled_from(["groq", "ollama_cloud"]),
            min_size=0,
            max_size=2,
            unique=True
        ),
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_failover_to_next_provider(self, failing_providers):
        """Property 4: Failover occurs when providers fail."""
        providers = {}
        
        for name in ["groq", "ollama_cloud", "ollama_local"]:
            provider = create_mock_provider(name, True)
            
            if name in failing_providers:
                # Make this provider fail
                provider.generate = AsyncMock(side_effect=Exception(f"{name} failed"))
            
            providers[name] = provider
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=["groq", "ollama_cloud", "ollama_local"],
        )
        
        messages = [{"role": "user", "content": "test"}]
        response = await manager.generate_with_failover(messages)
        
        # Should get a response from a non-failing provider
        assert response is not None
        assert response.provider not in failing_providers
    
    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_error(self):
        """AllProvidersFailedError raised when all fail."""
        from src.llm.provider_manager import AllProvidersFailedError
        
        providers = {
            "groq": create_mock_provider("groq", True),
            "ollama_cloud": create_mock_provider("ollama_cloud", True),
        }
        
        # Make all providers fail
        for provider in providers.values():
            provider.generate = AsyncMock(side_effect=Exception("failed"))
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
        )
        
        messages = [{"role": "user", "content": "test"}]
        
        with pytest.raises(AllProvidersFailedError):
            await manager.generate_with_failover(messages)


class TestProviderRecoveryRestoresPriority:
    """Property 5: Provider Recovery Restores Priority
    
    For any provider marked unhealthy then later marked healthy, subsequent 
    calls to get_provider() SHALL consider that provider according to its 
    original priority.
    
    **Validates: Requirements 3.5**
    """
    
    @given(
        provider_to_recover=provider_name,
    )
    @settings(max_examples=50, deadline=None)
    def test_recovered_provider_regains_priority(self, provider_to_recover):
        """Property 5: Recovered provider is used according to priority."""
        providers = {
            "groq": create_mock_provider("groq", True),
            "ollama_cloud": create_mock_provider("ollama_cloud", True),
            "ollama_local": create_mock_provider("ollama_local", True),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=["groq", "ollama_cloud", "ollama_local"],
        )
        
        # Mark provider as unhealthy
        providers[provider_to_recover].is_healthy = False
        
        # Get provider (should skip unhealthy one)
        result1 = manager.get_provider()
        if provider_to_recover == "groq":
            assert result1.name != "groq"
        
        # Mark provider as healthy again
        providers[provider_to_recover].is_healthy = True
        
        # Get provider again
        result2 = manager.get_provider()
        
        # If recovered provider is highest priority, it should be returned
        if provider_to_recover == "groq":
            assert result2.name == "groq"


class TestProviderPreferenceSwitching:
    """Property 11: Provider Preference Switching
    
    For any valid provider name, calling ProviderManager.set_user_preference() 
    SHALL cause subsequent get_provider() calls to prefer that provider when healthy.
    
    **Validates: Requirements 6.2**
    """
    
    @given(
        user_id=user_id_strategy,
        preferred_provider=provider_name,
    )
    @settings(max_examples=100, deadline=None)
    def test_user_preference_respected(self, user_id, preferred_provider):
        """Property 11: User preference is respected when provider is healthy."""
        providers = {
            "groq": create_mock_provider("groq", True),
            "ollama_cloud": create_mock_provider("ollama_cloud", True),
            "ollama_local": create_mock_provider("ollama_local", True),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=["groq", "ollama_cloud", "ollama_local"],
        )
        
        # Set user preference
        success = manager.set_user_preference(user_id, preferred_provider)
        assert success is True
        
        # Get provider for this user
        result = manager.get_provider(user_id)
        
        # Should return preferred provider
        assert result is not None
        assert result.name == preferred_provider
    
    @given(
        user_id=user_id_strategy,
        preferred_provider=provider_name,
    )
    @settings(max_examples=50, deadline=None)
    def test_preference_falls_back_when_unhealthy(self, user_id, preferred_provider):
        """Falls back to priority order when preferred provider is unhealthy."""
        providers = {
            "groq": create_mock_provider("groq", True),
            "ollama_cloud": create_mock_provider("ollama_cloud", True),
            "ollama_local": create_mock_provider("ollama_local", True),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
            priority_order=["groq", "ollama_cloud", "ollama_local"],
        )
        
        # Set preference and then mark it unhealthy
        manager.set_user_preference(user_id, preferred_provider)
        providers[preferred_provider].is_healthy = False
        
        # Get provider
        result = manager.get_provider(user_id)
        
        # Should NOT return unhealthy preferred provider
        assert result is not None
        assert result.name != preferred_provider
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_invalid_provider_preference_rejected(self, user_id):
        """Setting preference to invalid provider returns False."""
        providers = {
            "groq": create_mock_provider("groq", True),
        }
        
        manager = ProviderManager(
            providers=providers,
            rate_limiter=create_rate_limiter(),
        )
        
        # Try to set preference to non-existent provider
        success = manager.set_user_preference(user_id, "nonexistent")
        assert success is False
