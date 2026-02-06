"""Audit logging for security-relevant events in OpenClaw Telegram Bot."""

import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Optional


# Patterns that should never appear in logs
SENSITIVE_PATTERNS = [
    "api_key",
    "token",
    "password",
    "secret",
    "credential",
]


class AuditLogger:
    """Handles security-relevant event logging with rotating files."""
    
    def __init__(
        self,
        log_path: str = "logs/audit.log",
        retention_days: int = 30,
        log_level: int = logging.INFO,
    ):
        """Initialize AuditLogger.
        
        Args:
            log_path: Path to audit log file
            retention_days: Number of days to retain log files
            log_level: Logging level
        """
        self.log_path = Path(log_path)
        self.retention_days = retention_days
        self.logger = logging.getLogger("openclaw.audit")
        self.logger.setLevel(log_level)
        self._setup_rotating_handler()
    
    def _setup_rotating_handler(self) -> None:
        """Configure rotating file handler."""
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create rotating handler (rotates daily, keeps retention_days backups)
        handler = TimedRotatingFileHandler(
            self.log_path,
            when="midnight",
            interval=1,
            backupCount=self.retention_days,
            encoding="utf-8",
        )
        
        # Format: timestamp | event_type | structured_data
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
    
    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive data from log entries.
        
        Args:
            data: Data dictionary to sanitize
            
        Returns:
            Sanitized copy of data
        """
        sanitized = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive patterns
            if any(pattern in key_lower for pattern in SENSITIVE_PATTERNS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, str):
                # Check if value looks like a token/key (long alphanumeric)
                if len(value) > 20 and value.isalnum():
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _log_event(
        self,
        event_type: str,
        data: dict[str, Any],
        level: int = logging.INFO,
    ) -> None:
        """Log a structured event.
        
        Args:
            event_type: Type of event (e.g., "AUTH_ATTEMPT", "ADMIN_CMD")
            data: Event data dictionary
            level: Log level
        """
        sanitized = self._sanitize_data(data)
        sanitized["event_type"] = event_type
        sanitized["timestamp"] = datetime.now().isoformat()
        
        message = json.dumps(sanitized, default=str)
        self.logger.log(level, message)
    
    def log_auth_attempt(
        self,
        user_id: int,
        success: bool,
        reason: str = "",
    ) -> None:
        """Log authentication attempt.
        
        Args:
            user_id: Telegram user ID
            success: Whether authentication succeeded
            reason: Reason for failure (if applicable)
        """
        self._log_event(
            "AUTH_ATTEMPT",
            {
                "user_id": user_id,
                "success": success,
                "reason": reason,
            },
            level=logging.INFO if success else logging.WARNING,
        )
    
    def log_admin_command(
        self,
        user_id: int,
        command: str,
        args: list[str],
    ) -> None:
        """Log admin command execution.
        
        Args:
            user_id: Telegram user ID of admin
            command: Command name (e.g., "/reload")
            args: Command arguments (sanitized)
        """
        # Sanitize args to remove potential sensitive data
        safe_args = [
            "[REDACTED]" if any(p in str(a).lower() for p in SENSITIVE_PATTERNS)
            else str(a)
            for a in args
        ]
        
        self._log_event(
            "ADMIN_COMMAND",
            {
                "user_id": user_id,
                "command": command,
                "args": safe_args,
            },
        )
    
    def log_failover(
        self,
        from_provider: str,
        to_provider: str,
        reason: str,
    ) -> None:
        """Log provider failover event.
        
        Args:
            from_provider: Source provider name
            to_provider: Target provider name
            reason: Reason for failover
        """
        self._log_event(
            "PROVIDER_FAILOVER",
            {
                "from_provider": from_provider,
                "to_provider": to_provider,
                "reason": reason,
            },
            level=logging.WARNING,
        )
    
    def log_rate_limit(
        self,
        user_id: int,
        provider: str,
        limit_type: str,
    ) -> None:
        """Log rate limit violation.
        
        Args:
            user_id: Telegram user ID
            provider: Provider that hit rate limit
            limit_type: Type of limit ("rpm" or "tpm")
        """
        self._log_event(
            "RATE_LIMIT",
            {
                "user_id": user_id,
                "provider": provider,
                "limit_type": limit_type,
            },
            level=logging.WARNING,
        )
    
    def log_startup(self, version: str, providers: list[str]) -> None:
        """Log bot startup.
        
        Args:
            version: Bot version
            providers: List of enabled provider names
        """
        self._log_event(
            "BOT_STARTUP",
            {
                "version": version,
                "enabled_providers": providers,
            },
        )
    
    def log_shutdown(self, reason: str = "normal") -> None:
        """Log bot shutdown.
        
        Args:
            reason: Reason for shutdown
        """
        self._log_event(
            "BOT_SHUTDOWN",
            {
                "reason": reason,
            },
        )
