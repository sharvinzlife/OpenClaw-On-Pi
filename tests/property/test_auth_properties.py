"""Property-based tests for AuthManager.

Feature: openclaw-telegram-bot
Tests Properties 13 and 14 from the design document.
"""

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from src.security.auth import AuthManager, AuthSettings, PERMISSION_LEVELS


# Strategies
user_id_strategy = st.integers(min_value=1, max_value=10**12)
permission_level = st.sampled_from(["admin", "user", "guest"])


@st.composite
def permissions_dict(draw, min_users=0, max_users=20):
    """Generate a permissions dictionary."""
    num_users = draw(st.integers(min_value=min_users, max_value=max_users))
    user_ids = draw(st.lists(
        user_id_strategy,
        min_size=num_users,
        max_size=num_users,
        unique=True
    ))
    levels = draw(st.lists(
        permission_level,
        min_size=num_users,
        max_size=num_users
    ))
    return dict(zip(user_ids, levels))


@st.composite
def auth_settings(draw):
    """Generate valid auth settings."""
    return AuthSettings(
        allow_unknown_users=draw(st.booleans()),
        guest_rate_limit=draw(st.integers(min_value=1, max_value=100)),
        user_rate_limit=draw(st.integers(min_value=1, max_value=100)),
        admin_rate_limit=draw(st.integers(min_value=1, max_value=100)),
        auth_failure_lockout=draw(st.integers(min_value=1, max_value=20)),
        lockout_duration_minutes=draw(st.integers(min_value=1, max_value=60)),
    )


class TestUserAuthorizationAgainstAllowlist:
    """Property 13: User Authorization Against Allowlist
    
    For any Telegram user ID, AuthManager.is_authorized(user_id) SHALL return 
    True if and only if the user_id appears in the permissions.yaml allowlist 
    (admins, users, or guests).
    
    **Validates: Requirements 8.1, 8.3**
    """
    
    @given(
        permissions=permissions_dict(min_users=1, max_users=20),
        test_user_id=user_id_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_authorized_iff_in_allowlist(self, permissions, test_user_id):
        """Property 13: User is authorized iff in allowlist (allow_unknown=False)."""
        settings = AuthSettings(allow_unknown_users=False)
        manager = AuthManager(permissions, settings)
        
        is_in_allowlist = test_user_id in permissions
        is_authorized = manager.is_authorized(test_user_id)
        
        assert is_authorized == is_in_allowlist, (
            f"User {test_user_id} authorization mismatch: "
            f"in_allowlist={is_in_allowlist}, is_authorized={is_authorized}"
        )
    
    @given(
        permissions=permissions_dict(min_users=0, max_users=10),
        test_user_id=user_id_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_unknown_users_authorized_when_allowed(self, permissions, test_user_id):
        """Unknown users are authorized when allow_unknown_users=True."""
        settings = AuthSettings(allow_unknown_users=True)
        manager = AuthManager(permissions, settings)
        
        # All users should be authorized when allow_unknown_users=True
        assert manager.is_authorized(test_user_id) is True
    
    @given(
        permissions=permissions_dict(min_users=1, max_users=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_all_allowlist_users_authorized(self, permissions):
        """All users in allowlist are authorized."""
        settings = AuthSettings(allow_unknown_users=False)
        manager = AuthManager(permissions, settings)
        
        for user_id in permissions:
            assert manager.is_authorized(user_id) is True, (
                f"User {user_id} in allowlist should be authorized"
            )
    
    @given(
        permissions=permissions_dict(min_users=1, max_users=10),
        required_level=permission_level,
    )
    @settings(max_examples=100, deadline=None)
    def test_permission_level_hierarchy(self, permissions, required_level):
        """Higher permission levels can access lower level commands."""
        settings = AuthSettings(allow_unknown_users=False)
        manager = AuthManager(permissions, settings)
        
        required_value = PERMISSION_LEVELS[required_level]
        
        for user_id, user_level in permissions.items():
            user_value = PERMISSION_LEVELS[user_level]
            has_permission = manager.check_permission(user_id, required_level)
            
            expected = user_value >= required_value
            assert has_permission == expected, (
                f"User {user_id} with level {user_level} ({user_value}) "
                f"checking {required_level} ({required_value}): "
                f"expected {expected}, got {has_permission}"
            )


class TestAuthFailureRateLimiting:
    """Property 14: Auth Failure Rate Limiting
    
    For any user who has recorded N failed authentication attempts where 
    N >= auth_failure_lockout threshold, AuthManager.is_rate_limited(user_id) 
    SHALL return True until the lockout duration expires.
    
    **Validates: Requirements 8.5**
    """
    
    @given(
        user_id=user_id_strategy,
        lockout_threshold=st.integers(min_value=1, max_value=10),
        num_failures=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_rate_limited_after_threshold_failures(
        self, user_id, lockout_threshold, num_failures
    ):
        """Property 14: User is rate limited after N >= threshold failures."""
        settings = AuthSettings(
            auth_failure_lockout=lockout_threshold,
            lockout_duration_minutes=15,
        )
        manager = AuthManager({}, settings)
        
        # Record failures
        for _ in range(num_failures):
            manager.record_failed_attempt(user_id)
        
        is_limited = manager.is_rate_limited(user_id)
        should_be_limited = num_failures >= lockout_threshold
        
        assert is_limited == should_be_limited, (
            f"After {num_failures} failures with threshold {lockout_threshold}: "
            f"expected rate_limited={should_be_limited}, got {is_limited}"
        )
    
    @given(
        user_id=user_id_strategy,
        lockout_threshold=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_not_rate_limited_below_threshold(self, user_id, lockout_threshold):
        """User is not rate limited with fewer than threshold failures."""
        settings = AuthSettings(
            auth_failure_lockout=lockout_threshold,
            lockout_duration_minutes=15,
        )
        manager = AuthManager({}, settings)
        
        # Record one less than threshold
        for _ in range(lockout_threshold - 1):
            manager.record_failed_attempt(user_id)
        
        assert manager.is_rate_limited(user_id) is False
    
    @given(
        user_id=user_id_strategy,
        lockout_threshold=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_rate_limited_exactly_at_threshold(self, user_id, lockout_threshold):
        """User is rate limited at exactly threshold failures."""
        settings = AuthSettings(
            auth_failure_lockout=lockout_threshold,
            lockout_duration_minutes=15,
        )
        manager = AuthManager({}, settings)
        
        # Record exactly threshold failures
        for _ in range(lockout_threshold):
            manager.record_failed_attempt(user_id)
        
        assert manager.is_rate_limited(user_id) is True
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_clear_failed_attempts_removes_lockout(self, user_id):
        """Clearing failed attempts removes rate limiting."""
        settings = AuthSettings(
            auth_failure_lockout=3,
            lockout_duration_minutes=15,
        )
        manager = AuthManager({}, settings)
        
        # Lock out the user
        for _ in range(5):
            manager.record_failed_attempt(user_id)
        
        assert manager.is_rate_limited(user_id) is True
        
        # Clear attempts
        manager.clear_failed_attempts(user_id)
        
        assert manager.is_rate_limited(user_id) is False
    
    @given(
        user_id1=user_id_strategy,
        user_id2=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_rate_limiting_isolated_between_users(self, user_id1, user_id2):
        """Rate limiting for one user doesn't affect another."""
        # Ensure different users
        if user_id1 == user_id2:
            user_id2 = user_id1 + 1
        
        settings = AuthSettings(
            auth_failure_lockout=3,
            lockout_duration_minutes=15,
        )
        manager = AuthManager({}, settings)
        
        # Lock out user1
        for _ in range(5):
            manager.record_failed_attempt(user_id1)
        
        # user1 should be limited, user2 should not
        assert manager.is_rate_limited(user_id1) is True
        assert manager.is_rate_limited(user_id2) is False
