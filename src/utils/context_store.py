"""Conversation context management for OpenClaw Telegram Bot."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Conversation history for a single user."""

    user_id: int
    messages: list[dict[str, str]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    total_tokens: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class ContextStore:
    """Manages per-user conversation history with persistence."""

    def __init__(
        self,
        storage_path: str = "data/contexts.json",
        max_messages: int = 10,
        max_tokens: int = 4000,
    ):
        """Initialize ContextStore.

        Args:
            storage_path: Path to persist contexts
            max_messages: Maximum messages per user context
            max_tokens: Maximum tokens per user context
        """
        self.storage_path = Path(storage_path)
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.contexts: dict[int, ConversationContext] = {}

    def get_context(self, user_id: int) -> list[dict[str, str]]:
        """Get conversation history for user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of message dicts with 'role' and 'content'
        """
        if user_id not in self.contexts:
            return []

        return self.contexts[user_id].messages.copy()

    def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        tokens: int = 0,
    ) -> None:
        """Add message to user's context.

        Args:
            user_id: Telegram user ID
            role: Message role ('user' or 'assistant')
            content: Message content
            tokens: Token count for this message
        """
        if user_id not in self.contexts:
            self.contexts[user_id] = ConversationContext(user_id=user_id)

        context = self.contexts[user_id]
        context.messages.append({"role": role, "content": content})
        context.total_tokens += tokens
        context.updated_at = datetime.now().isoformat()

        # Truncate if needed
        self._truncate_context(context)

    def clear_context(self, user_id: int) -> None:
        """Clear user's conversation history.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self.contexts:
            del self.contexts[user_id]
            logger.debug(f"Cleared context for user {user_id}")

    def _truncate_context(self, context: ConversationContext) -> None:
        """Remove oldest messages to stay within limits.

        Preserves the most recent messages while respecting max_messages
        and max_tokens limits.

        Args:
            context: ConversationContext to truncate
        """
        # Truncate by message count
        while len(context.messages) > self.max_messages:
            context.messages.pop(0)

        # Note: Token-based truncation would require tracking per-message tokens
        # For simplicity, we rely on message count as primary limit

    def save_to_disk(self) -> None:
        """Persist all contexts to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {str(user_id): asdict(context) for user_id, context in self.contexts.items()}

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Saved {len(self.contexts)} contexts to {self.storage_path}")

    def load_from_disk(self) -> None:
        """Load contexts from disk."""
        if not self.storage_path.exists():
            logger.debug(f"No context file found at {self.storage_path}")
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            self.contexts = {}
            for user_id_str, context_data in data.items():
                user_id = int(user_id_str)
                self.contexts[user_id] = ConversationContext(
                    user_id=user_id,
                    messages=context_data.get("messages", []),
                    created_at=context_data.get("created_at", ""),
                    updated_at=context_data.get("updated_at", ""),
                    total_tokens=context_data.get("total_tokens", 0),
                )

            logger.info(f"Loaded {len(self.contexts)} contexts from {self.storage_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse context file: {e}")
            self.contexts = {}
        except Exception as e:
            logger.error(f"Failed to load contexts: {e}")
            self.contexts = {}

    def get_all_user_ids(self) -> list[int]:
        """Get list of all user IDs with stored contexts.

        Returns:
            List of user IDs
        """
        return list(self.contexts.keys())

    def get_context_stats(self, user_id: int) -> dict:
        """Get statistics for a user's context.

        Args:
            user_id: Telegram user ID

        Returns:
            Dict with message count, token count, etc.
        """
        if user_id not in self.contexts:
            return {
                "message_count": 0,
                "total_tokens": 0,
                "created_at": None,
                "updated_at": None,
            }

        context = self.contexts[user_id]
        return {
            "message_count": len(context.messages),
            "total_tokens": context.total_tokens,
            "created_at": context.created_at,
            "updated_at": context.updated_at,
        }
