"""Authentication and authorization for OpenClaw Telegram Bot."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Permission level hierarchy (higher value = more permissions)
PERMISSION_LEVELS = {
    "guest": 1,
    "user": 2,
    "admin": 3,
}


@dataclass
class UserPermission:
    """Permission data for a single user."""
    
    user_id: int
    level: str  # "admin", "user", "guest"
    rate_limit: int  # requests per minute


@dataclass
class AuthSettings:
    """Authentication-related settings."""
    
    allow_unknown_users: bool = False
    guest_rate_limit: int = 5
    user_rate_limit: int = 20
    admin_rate_limit: int = 100
    auth_failure_lockout: int = 5
    lockout_duration_minutes: int = 15


class AuthManager:
    """Handles user authentication and authorization."""
    
    def __init__(
        self,
        permissions: dict[int, str],
        settings: Optional[AuthSettings] = None,
    ):
        """Initialize AuthManager.
        
        Args:
            permissions: Dict mapping user_id to permission level
            settings: Authentication settings
        """
        self.permissions = permissions
        self.settings = settings or AuthSettings()
        self.failed_attempts: dict[int, list[datetime]] = {}
        self._user_cache: dict[int, UserPermission] = {}
        self._build_user_cache()
    
    def _build_user_cache(self) -> None:
        """Build user permission cache with rate limits."""
        self._user_cache = {}
        
        rate_limits = {
            "admin": self.settings.admin_rate_limit,
            "user": self.settings.user_rate_limit,
            "guest": self.settings.guest_rate_limit,
        }
        
        for user_id, level in self.permissions.items():
            self._user_cache[user_id] = UserPermission(
                user_id=user_id,
                level=level,
                rate_limit=rate_limits.get(level, self.settings.guest_rate_limit),
            )
    
    def load_permissions(self, permissions: dict[int, str]) -> None:
        """Reload permissions from new data.
        
        Args:
            permissions: Dict mapping user_id to permission level
        """
        self.permissions = permissions
        self._build_user_cache()
        logger.info(f"Reloaded permissions for {len(permissions)} users")
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is in the allowlist.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is authorized, False otherwise
        """
        # Check if user is in explicit allowlist
        if user_id in self.permissions:
            return True
        
        # Check if unknown users are allowed
        if self.settings.allow_unknown_users:
            return True
        
        return False
    
    def check_permission(self, user_id: int, required_level: str) -> bool:
        """Check if user has required permission level.
        
        Args:
            user_id: Telegram user ID
            required_level: Required permission level ("guest", "user", "admin")
            
        Returns:
            True if user has sufficient permissions
        """
        if not self.is_authorized(user_id):
            return False
        
        user_level = self.get_permission_level(user_id)
        required_value = PERMISSION_LEVELS.get(required_level, 0)
        user_value = PERMISSION_LEVELS.get(user_level, 0)
        
        return user_value >= required_value
    
    def get_permission_level(self, user_id: int) -> str:
        """Get user's permission level.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Permission level string
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id].level
        
        # Unknown users get guest level if allowed
        if self.settings.allow_unknown_users:
            return "guest"
        
        return ""
    
    def get_rate_limit(self, user_id: int) -> int:
        """Get user's rate limit (requests per minute).
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Rate limit value
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id].rate_limit
        
        return self.settings.guest_rate_limit
    
    def record_failed_attempt(self, user_id: int) -> None:
        """Record a failed authentication attempt.
        
        Args:
            user_id: Telegram user ID
        """
        now = datetime.now()
        
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []
        
        self.failed_attempts[user_id].append(now)
        
        # Clean up old attempts outside lockout window
        cutoff = now - timedelta(minutes=self.settings.lockout_duration_minutes)
        self.failed_attempts[user_id] = [
            t for t in self.failed_attempts[user_id] if t > cutoff
        ]
        
        logger.debug(
            f"Recorded failed auth attempt for user {user_id}, "
            f"total recent: {len(self.failed_attempts[user_id])}"
        )
    
    def is_rate_limited(self, user_id: int) -> bool:
        """Check if user has exceeded auth failure rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is locked out due to too many failures
        """
        if user_id not in self.failed_attempts:
            return False
        
        now = datetime.now()
        cutoff = now - timedelta(minutes=self.settings.lockout_duration_minutes)
        
        # Count recent failures
        recent_failures = [
            t for t in self.failed_attempts[user_id] if t > cutoff
        ]
        
        return len(recent_failures) >= self.settings.auth_failure_lockout
    
    def get_lockout_remaining(self, user_id: int) -> Optional[timedelta]:
        """Get remaining lockout time for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Remaining lockout duration, or None if not locked out
        """
        if not self.is_rate_limited(user_id):
            return None
        
        if user_id not in self.failed_attempts or not self.failed_attempts[user_id]:
            return None
        
        # Find the oldest failure in the current lockout window
        oldest_failure = min(self.failed_attempts[user_id])
        lockout_end = oldest_failure + timedelta(minutes=self.settings.lockout_duration_minutes)
        remaining = lockout_end - datetime.now()
        
        return remaining if remaining.total_seconds() > 0 else None
    
    def clear_failed_attempts(self, user_id: int) -> None:
        """Clear failed attempts for a user (e.g., after successful auth).
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self.failed_attempts:
            del self.failed_attempts[user_id]
