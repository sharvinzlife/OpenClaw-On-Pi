"""Property-based tests for RateLimiter.

Feature: openclaw-telegram-bot
Tests Properties 6, 7, and 8 from the design document.
"""

import pytest
from hypothesis import given, settings, strategies as st

from src.llm.rate_limiter import RateLimiter, RateLimitConfig


# Strategies
provider_name = st.sampled_from(["groq", "ollama_cloud", "ollama_local"])
positive_int = st.integers(min_value=1, max_value=1000)
token_count = st.integers(min_value=1, max_value=10000)


@st.composite
def rate_limit_config(draw):
    """Generate valid rate limit configuration."""
    return RateLimitConfig(
        requests_per_minute=draw(st.integers(min_value=1, max_value=100)),
        tokens_per_minute=draw(st.integers(min_value=100, max_value=100000)),
    )


class TestRateLimitEnforcement:
    """Property 6: Rate Limit Enforcement
    
    For any sequence of N requests where N exceeds the configured 
    requests_per_minute limit, RateLimiter.can_request() SHALL return 
    False for requests beyond the limit within the same minute window.
    
    **Validates: Requirements 4.1**
    """
    
    @given(
        rpm_limit=st.integers(min_value=1, max_value=50),
        num_requests=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100, deadline=None)
    def test_requests_blocked_after_limit(self, rpm_limit, num_requests):
        """Property 6: Requests beyond RPM limit are blocked."""
        config = RateLimitConfig(
            requests_per_minute=rpm_limit,
            tokens_per_minute=1000000,  # High enough to not interfere
        )
        limiter = RateLimiter({"test": config})
        
        # Record requests up to the limit
        for i in range(num_requests):
            can_request = limiter.can_request("test")
            
            if i < rpm_limit:
                # Should be allowed before hitting limit
                assert can_request is True, f"Request {i+1} should be allowed (limit={rpm_limit})"
                limiter.record_request("test", tokens=0)
            else:
                # Should be blocked after hitting limit
                assert can_request is False, f"Request {i+1} should be blocked (limit={rpm_limit})"
    
    @given(
        rpm_limit=st.integers(min_value=5, max_value=30),
    )
    @settings(max_examples=50, deadline=None)
    def test_exactly_at_limit_allowed(self, rpm_limit):
        """Requests up to exactly the limit are allowed."""
        config = RateLimitConfig(
            requests_per_minute=rpm_limit,
            tokens_per_minute=1000000,
        )
        limiter = RateLimiter({"test": config})
        
        # Should be able to make exactly rpm_limit requests
        for i in range(rpm_limit):
            assert limiter.can_request("test") is True
            limiter.record_request("test")
        
        # The next one should be blocked
        assert limiter.can_request("test") is False


class TestProactiveFailoverThreshold:
    """Property 7: Proactive Failover Threshold
    
    For any provider usage level above 80% of its rate limit, 
    RateLimiter.should_failover() SHALL return True.
    
    **Validates: Requirements 4.3**
    """
    
    @given(
        rpm_limit=st.integers(min_value=10, max_value=100),
        threshold=st.floats(min_value=0.1, max_value=0.99),
    )
    @settings(max_examples=100, deadline=None)
    def test_failover_triggered_above_threshold(self, rpm_limit, threshold):
        """Property 7: Failover triggered when usage exceeds threshold."""
        config = RateLimitConfig(
            requests_per_minute=rpm_limit,
            tokens_per_minute=1000000,
        )
        limiter = RateLimiter({"test": config})
        
        # Calculate how many requests to reach threshold
        requests_for_threshold = int(rpm_limit * threshold)
        
        # Record requests just below threshold
        for _ in range(requests_for_threshold):
            limiter.record_request("test")
        
        usage = limiter.get_usage_percentage("test")
        should_failover = limiter.should_failover("test", threshold=threshold)
        
        # If usage >= threshold, should_failover should be True
        if usage["rpm"] >= threshold:
            assert should_failover is True, (
                f"Should failover at {usage['rpm']:.2%} usage with {threshold:.2%} threshold"
            )
    
    @given(
        rpm_limit=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=50, deadline=None)
    def test_failover_at_80_percent_default(self, rpm_limit):
        """Default 80% threshold triggers failover correctly."""
        config = RateLimitConfig(
            requests_per_minute=rpm_limit,
            tokens_per_minute=1000000,
        )
        limiter = RateLimiter({"test": config})
        
        # Record enough requests to reach 80%
        # Use ceiling to ensure we actually hit 80%
        import math
        requests_at_80 = math.ceil(rpm_limit * 0.8)
        for _ in range(requests_at_80):
            limiter.record_request("test")
        
        # At or above 80%, should trigger failover
        usage = limiter.get_usage_percentage("test")
        if usage["rpm"] >= 0.8:
            assert limiter.should_failover("test") is True
    
    @given(
        rpm_limit=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=50, deadline=None)
    def test_no_failover_below_threshold(self, rpm_limit):
        """No failover when usage is below threshold."""
        config = RateLimitConfig(
            requests_per_minute=rpm_limit,
            tokens_per_minute=1000000,
        )
        limiter = RateLimiter({"test": config})
        
        # Record only 50% of requests
        requests_at_50 = int(rpm_limit * 0.5)
        for _ in range(requests_at_50):
            limiter.record_request("test")
        
        # At 50%, should NOT trigger failover (default threshold is 80%)
        assert limiter.should_failover("test") is False


class TestTokenUsageTrackingAccuracy:
    """Property 8: Token Usage Tracking Accuracy
    
    For any request recorded with RateLimiter.record_request(provider, tokens), 
    the subsequent call to get_usage_percentage() SHALL reflect the added 
    tokens in the usage calculation.
    
    **Validates: Requirements 4.4**
    """
    
    @given(
        tpm_limit=st.integers(min_value=1000, max_value=100000),
        token_amounts=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=1,
            max_size=20
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_token_usage_accurately_tracked(self, tpm_limit, token_amounts):
        """Property 8: Token usage is accurately reflected in usage percentage."""
        config = RateLimitConfig(
            requests_per_minute=1000,  # High enough to not interfere
            tokens_per_minute=tpm_limit,
        )
        limiter = RateLimiter({"test": config})
        
        total_tokens = 0
        for tokens in token_amounts:
            limiter.record_request("test", tokens=tokens)
            total_tokens += tokens
            
            usage = limiter.get_usage_percentage("test")
            expected_tpm = total_tokens / tpm_limit
            
            # Allow small floating point tolerance
            assert abs(usage["tpm"] - expected_tpm) < 0.001, (
                f"Token usage mismatch: expected {expected_tpm:.4f}, got {usage['tpm']:.4f}"
            )
    
    @given(
        tpm_limit=st.integers(min_value=1000, max_value=50000),
        tokens=st.integers(min_value=100, max_value=5000),
    )
    @settings(max_examples=50, deadline=None)
    def test_single_request_token_tracking(self, tpm_limit, tokens):
        """Single request tokens are tracked correctly."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=tpm_limit,
        )
        limiter = RateLimiter({"test": config})
        
        # Before recording
        usage_before = limiter.get_usage_percentage("test")
        assert usage_before["tpm"] == 0.0
        
        # Record request with tokens
        limiter.record_request("test", tokens=tokens)
        
        # After recording
        usage_after = limiter.get_usage_percentage("test")
        expected = tokens / tpm_limit
        
        assert abs(usage_after["tpm"] - expected) < 0.001
    
    @given(
        tpm_limit=st.integers(min_value=1000, max_value=50000),
    )
    @settings(max_examples=50, deadline=None)
    def test_current_usage_returns_exact_counts(self, tpm_limit):
        """get_current_usage returns exact token counts."""
        config = RateLimitConfig(
            requests_per_minute=100,
            tokens_per_minute=tpm_limit,
        )
        limiter = RateLimiter({"test": config})
        
        # Record specific amounts
        limiter.record_request("test", tokens=100)
        limiter.record_request("test", tokens=200)
        limiter.record_request("test", tokens=300)
        
        usage = limiter.get_current_usage("test")
        
        assert usage["requests"] == 3
        assert usage["tokens"] == 600
