"""Base skill interface for OpenClaw bot skills."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SkillResult:
    """Result from a skill execution."""

    text: Optional[str] = None
    file_path: Optional[str] = None  # For skills that send files
    error: Optional[str] = None


@dataclass
class SkillStats:
    """Per-skill usage statistics."""

    name: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None


class BaseSkill(ABC):
    """Base class for all bot skills.

    Subclasses MUST set the class attributes: name, command, description.
    Optionally override permission_level (defaults to "user").
    """

    # Subclasses MUST set these
    name: str = ""
    command: str = ""
    description: str = ""
    permission_level: str = "user"  # "guest", "user", "admin"

    def __init__(self, config: dict):
        """Initialize with skill-specific config from skills.yaml.

        Args:
            config: Skill-specific configuration dictionary.
        """
        self.config = config
        self.enabled: bool = config.get("enabled", True)

    @abstractmethod
    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        """Execute the skill command.

        Args:
            user_id: Telegram user ID.
            args: Command arguments (text after /command).
            **kwargs: Extra context (e.g., message object for /ocr).

        Returns:
            SkillResult with text response, file path, or error.
        """
        pass

    @classmethod
    def check_dependencies(cls) -> bool:
        """Check if required libraries are installed.

        Override in subclasses that depend on external packages.

        Returns:
            True if all dependencies are available.
        """
        return True
