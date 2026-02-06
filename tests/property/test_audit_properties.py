"""Property-based tests for AuditLogger.

Feature: openclaw-telegram-bot
Tests Properties 18 and 19 from the design document.
"""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from src.utils.audit_logger import AuditLogger, SENSITIVE_PATTERNS


# Strategies
user_id_strategy = st.integers(min_value=1, max_value=10**12)
provider_name = st.sampled_from(["groq", "ollama_cloud", "ollama_local"])
command_name = st.sampled_from(["/providers", "/costs", "/limits", "/reload"])
limit_type = st.sampled_from(["rpm", "tpm"])


@st.composite
def safe_text(draw, min_size=1, max_size=50):
    """Generate text that doesn't contain sensitive patterns."""
    text = draw(st.text(
        min_size=min_size,
        max_size=max_size,
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'))
    ))
    # Filter out any text that accidentally contains sensitive patterns
    for pattern in SENSITIVE_PATTERNS:
        if pattern in text.lower():
            return "safe_text"
    return text if text.strip() else "default"


class TestAuditLoggingCompleteness:
    """Property 18: Audit Logging Completeness
    
    For any security-relevant event (auth attempt, admin command, failover, 
    rate limit violation), the corresponding AuditLogger method SHALL write 
    a log entry containing the event type, timestamp, and relevant identifiers.
    
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    """
    
    @given(
        user_id=user_id_strategy,
        success=st.booleans(),
        reason=safe_text(),
    )
    @settings(max_examples=50, deadline=None)
    def test_auth_attempt_logged_completely(self, user_id, success, reason):
        """Property 18: Auth attempts contain required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            logger.log_auth_attempt(user_id, success, reason)
            
            # Read and parse log
            content = log_path.read_text()
            assert content, "Log file should not be empty"
            
            # Parse the JSON part (after the timestamp and level)
            log_line = content.strip().split(" | ")[-1]
            log_data = json.loads(log_line)
            
            # Verify required fields
            assert log_data["event_type"] == "AUTH_ATTEMPT"
            assert "timestamp" in log_data
            assert log_data["user_id"] == user_id
            assert log_data["success"] == success
    
    @given(
        user_id=user_id_strategy,
        command=command_name,
        args=st.lists(safe_text(), min_size=0, max_size=3),
    )
    @settings(max_examples=50, deadline=None)
    def test_admin_command_logged_completely(self, user_id, command, args):
        """Property 18: Admin commands contain required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            logger.log_admin_command(user_id, command, args)
            
            content = log_path.read_text()
            log_line = content.strip().split(" | ")[-1]
            log_data = json.loads(log_line)
            
            assert log_data["event_type"] == "ADMIN_COMMAND"
            assert "timestamp" in log_data
            assert log_data["user_id"] == user_id
            assert log_data["command"] == command
    
    @given(
        from_provider=provider_name,
        to_provider=provider_name,
        reason=safe_text(),
    )
    @settings(max_examples=50, deadline=None)
    def test_failover_logged_completely(self, from_provider, to_provider, reason):
        """Property 18: Failover events contain required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            logger.log_failover(from_provider, to_provider, reason)
            
            content = log_path.read_text()
            log_line = content.strip().split(" | ")[-1]
            log_data = json.loads(log_line)
            
            assert log_data["event_type"] == "PROVIDER_FAILOVER"
            assert "timestamp" in log_data
            assert log_data["from_provider"] == from_provider
            assert log_data["to_provider"] == to_provider
    
    @given(
        user_id=user_id_strategy,
        provider=provider_name,
        limit=limit_type,
    )
    @settings(max_examples=50, deadline=None)
    def test_rate_limit_logged_completely(self, user_id, provider, limit):
        """Property 18: Rate limit violations contain required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            logger.log_rate_limit(user_id, provider, limit)
            
            content = log_path.read_text()
            log_line = content.strip().split(" | ")[-1]
            log_data = json.loads(log_line)
            
            assert log_data["event_type"] == "RATE_LIMIT"
            assert "timestamp" in log_data
            assert log_data["user_id"] == user_id
            assert log_data["provider"] == provider
            assert log_data["limit_type"] == limit


class TestSensitiveDataExclusion:
    """Property 19: Sensitive Data Exclusion from Logs
    
    For any log entry written by AuditLogger, the entry SHALL NOT contain 
    API keys, full message content, or personally identifiable information 
    beyond Telegram user IDs.
    
    **Validates: Requirements 11.6**
    """
    
    @given(
        user_id=user_id_strategy,
        api_key=st.text(min_size=20, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    )
    @settings(max_examples=50, deadline=None)
    def test_api_keys_redacted_in_args(self, user_id, api_key):
        """Property 19: API keys in command args are redacted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            # Try to log an admin command with an API key in args
            logger.log_admin_command(user_id, "/config", ["api_key=" + api_key])
            
            content = log_path.read_text()
            
            # The actual API key value should not appear in logs
            assert api_key not in content, "API key should be redacted from logs"
    
    @given(
        token=st.text(min_size=30, max_size=60, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    )
    @settings(max_examples=50, deadline=None)
    def test_long_alphanumeric_strings_redacted(self, token):
        """Property 19: Long alphanumeric strings (likely tokens) are redacted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            # Sanitize data directly
            data = {"some_field": token}
            sanitized = logger._sanitize_data(data)
            
            # Long alphanumeric strings should be redacted
            assert sanitized["some_field"] == "[REDACTED]", (
                f"Long alphanumeric string should be redacted: {token[:10]}..."
            )
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_sensitive_key_names_redacted(self, user_id):
        """Property 19: Fields with sensitive names are redacted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            # Test each sensitive pattern
            for pattern in SENSITIVE_PATTERNS:
                data = {
                    f"my_{pattern}": "sensitive_value_123",
                    "safe_field": "safe_value",
                }
                sanitized = logger._sanitize_data(data)
                
                assert sanitized[f"my_{pattern}"] == "[REDACTED]", (
                    f"Field containing '{pattern}' should be redacted"
                )
                assert sanitized["safe_field"] == "safe_value"
    
    @given(
        user_id=user_id_strategy,
        success=st.booleans(),
    )
    @settings(max_examples=50, deadline=None)
    def test_user_id_preserved_in_logs(self, user_id, success):
        """User IDs are preserved (they're allowed per requirements)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(str(log_path))
            
            logger.log_auth_attempt(user_id, success)
            
            content = log_path.read_text()
            log_line = content.strip().split(" | ")[-1]
            log_data = json.loads(log_line)
            
            # User ID should be preserved (it's allowed)
            assert log_data["user_id"] == user_id
