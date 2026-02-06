"""Property-based tests for CommandRouter.

Feature: openclaw-telegram-bot
Tests Properties 9 and 12 from the design document.
"""

import pytest
from hypothesis import given, settings, strategies as st

from src.bot.command_router import CommandRouter
from src.security.auth import AuthManager, AuthSettings, PERMISSION_LEVELS


# Strategies
user_id_strategy = st.integers(min_value=1, max_value=10**12)
permission_level = st.sampled_from(["admin", "user", "guest"])


def create_auth_manager(permissions: dict[int, str]) -> AuthManager:
    """Create an AuthManager with given permissions."""
    settings = AuthSettings(allow_unknown_users=False)
    return AuthManager(permissions, settings)


class TestPermissionBasedHelpFiltering:
    """Property 9: Permission-Based Help Filtering
    
    For any user with a given permission level (admin/user/guest), the /help 
    command response SHALL only include commands that user is authorized to execute.
    
    **Validates: Requirements 5.2**
    """
    
    @given(
        user_id=user_id_strategy,
        user_level=permission_level,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_help_shows_only_authorized_commands(self, user_id, user_level):
        """Property 9: Help only shows commands user can access."""
        permissions = {user_id: user_level}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        # Get available commands for this user
        available = router.get_available_commands(user_id)
        
        # Verify each available command is actually accessible
        for handler in available:
            required_level = handler.permission_level
            required_value = PERMISSION_LEVELS.get(required_level, 0)
            user_value = PERMISSION_LEVELS.get(user_level, 0)
            
            assert user_value >= required_value, (
                f"User with {user_level} ({user_value}) should not see "
                f"command requiring {required_level} ({required_value})"
            )
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_admin_sees_all_commands(self, user_id):
        """Admin users see all commands."""
        permissions = {user_id: "admin"}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        available = router.get_available_commands(user_id)
        all_commands = list(router.handlers.keys())
        
        # Admin should see all commands
        available_names = {h.name for h in available}
        assert available_names == set(all_commands)
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_guest_sees_limited_commands(self, user_id):
        """Guest users see only guest-level commands."""
        permissions = {user_id: "guest"}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        available = router.get_available_commands(user_id)
        
        # Guest should only see guest-level commands
        for handler in available:
            assert handler.permission_level == "guest", (
                f"Guest should not see {handler.name} (requires {handler.permission_level})"
            )
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_user_sees_user_and_guest_commands(self, user_id):
        """User-level users see user and guest commands."""
        permissions = {user_id: "user"}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        available = router.get_available_commands(user_id)
        
        # User should see user and guest commands, but not admin
        for handler in available:
            assert handler.permission_level in ["user", "guest"], (
                f"User should not see {handler.name} (requires {handler.permission_level})"
            )


class TestAdminCommandPermissionEnforcement:
    """Property 12: Admin Command Permission Enforcement
    
    For any user without admin permission level attempting an admin command 
    (/providers, /costs, /limits, /reload), the CommandRouter SHALL reject 
    the request and return an unauthorized error.
    
    **Validates: Requirements 7.4**
    """
    
    ADMIN_COMMANDS = ["providers", "costs", "limits", "reload"]
    
    @given(
        user_id=user_id_strategy,
        non_admin_level=st.sampled_from(["user", "guest"]),
        admin_command=st.sampled_from(ADMIN_COMMANDS),
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_non_admin_rejected_from_admin_commands(
        self, user_id, non_admin_level, admin_command
    ):
        """Property 12: Non-admin users rejected from admin commands."""
        permissions = {user_id: non_admin_level}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        response = await router.route(admin_command, user_id, [])
        
        # Should be rejected
        assert "permission" in response.lower() or "don't have" in response.lower(), (
            f"User with {non_admin_level} should be rejected from /{admin_command}. "
            f"Got: {response}"
        )
    
    @given(
        user_id=user_id_strategy,
        admin_command=st.sampled_from(ADMIN_COMMANDS),
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_admin_allowed_admin_commands(self, user_id, admin_command):
        """Admin users can access admin commands."""
        permissions = {user_id: "admin"}
        auth_manager = create_auth_manager(permissions)
        router = CommandRouter(auth_manager)
        
        response = await router.route(admin_command, user_id, [])
        
        # Should NOT be a permission error
        assert "permission" not in response.lower() or "don't have" not in response.lower(), (
            f"Admin should be allowed to use /{admin_command}. Got: {response}"
        )
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_unauthorized_user_rejected(self, user_id):
        """Users not in allowlist are rejected from all commands."""
        # Empty permissions - no one is authorized
        auth_manager = create_auth_manager({})
        router = CommandRouter(auth_manager)
        
        # Try any command
        response = await router.route("help", user_id, [])
        
        # Should be rejected
        assert "permission" in response.lower() or "don't have" in response.lower()
