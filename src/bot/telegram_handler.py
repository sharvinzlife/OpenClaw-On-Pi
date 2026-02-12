"""Telegram bot handler for OpenClaw."""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.ext import (
    CommandHandler as TGCommandHandler,
)

from ..llm.provider_manager import ProviderManager
from ..llm.rate_limiter import RateLimiter
from ..security.auth import AuthManager
from ..utils.audit_logger import AuditLogger
from ..utils.context_store import ContextStore
from ..web.dashboard import dashboard_state
from .command_router import CommandRouter

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Manages all Telegram API interactions."""

    def __init__(
        self,
        token: str,
        command_router: CommandRouter,
        auth_manager: AuthManager,
        provider_manager: ProviderManager,
        context_store: ContextStore,
        audit_logger: Optional[AuditLogger] = None,
        rate_limiter: Optional[RateLimiter] = None,
        streaming_interval_ms: int = 500,
        streaming_min_chars: int = 50,
        skill_registry=None,
    ):
        """Initialize TelegramHandler.

        Args:
            token: Telegram bot token
            command_router: CommandRouter for handling commands
            auth_manager: AuthManager for user verification
            provider_manager: ProviderManager for LLM requests
            context_store: ContextStore for conversation history
            audit_logger: Optional AuditLogger for security events
            rate_limiter: Optional RateLimiter for tracking API usage
            streaming_interval_ms: Interval for streaming updates
            streaming_min_chars: Minimum chars before streaming update
        """
        self.token = token
        self.command_router = command_router
        self.auth_manager = auth_manager
        self.provider_manager = provider_manager
        self.context_store = context_store
        self.audit_logger = audit_logger
        self.rate_limiter = rate_limiter
        self.streaming_interval_ms = streaming_interval_ms
        self.streaming_min_chars = streaming_min_chars

        self.skill_registry = skill_registry
        self.app: Optional[Application] = None
        self._running = False

    def _update_rate_limit_stats(self) -> None:
        """Update dashboard with current rate limit usage."""
        if not self.rate_limiter:
            return

        # Get Groq usage (primary provider)
        groq_usage = self.rate_limiter.get_current_usage("groq")
        groq_limits = self.rate_limiter.limits.get("groq")

        if groq_limits:
            dashboard_state.rate_limits = {
                "groq_rpm": {
                    "current": groq_usage["requests"],
                    "limit": groq_limits.requests_per_minute,
                },
                "groq_tpm": {
                    "current": groq_usage["tokens"],
                    "limit": groq_limits.tokens_per_minute,
                },
            }

    async def start(self) -> None:
        """Initialize and start the Telegram bot."""
        logger.info("Starting Telegram bot...")

        self.app = Application.builder().token(self.token).build()

        # Register command handlers
        for cmd_name in self.command_router.handlers:
            self.app.add_handler(TGCommandHandler(cmd_name, self._handle_command))

        # Register message handler for non-command messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Initialize and start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        self._running = True
        logger.info("Telegram bot started successfully")

    async def stop(self) -> None:
        """Gracefully shutdown the bot."""
        logger.info("Stopping Telegram bot...")

        self._running = False

        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

        # Save context on shutdown
        if self.context_store:
            self.context_store.save_to_disk()

        logger.info("Telegram bot stopped")

    async def _handle_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming command messages.

        Args:
            update: Telegram update object
            context: Telegram context
        """
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        text = update.message.text
        username = update.effective_user.username or str(user_id)

        # Parse command and args
        parts = text.split()
        command = parts[0][1:]  # Remove leading /
        args = parts[1:] if len(parts) > 1 else []

        # Check authorization
        if not self.auth_manager.is_authorized(user_id):
            if self.audit_logger:
                self.audit_logger.log_auth_attempt(user_id, False, "not in allowlist")

            self.auth_manager.record_failed_attempt(user_id)

            if self.auth_manager.is_rate_limited(user_id):
                await update.message.reply_text("Too many failed attempts. Please try again later.")
            else:
                await update.message.reply_text("You are not authorized to use this bot.")
            return

        # Log successful auth
        if self.audit_logger:
            self.audit_logger.log_auth_attempt(user_id, True)

        # Update dashboard stats
        dashboard_state.total_messages += 1
        dashboard_state.active_users.add(user_id)
        dashboard_state.add_activity("command", f"@{username}: /{command}", "⚡")

        # Route command — check if it's a skill with file output
        response_text = None
        if self.skill_registry and command in self.skill_registry.skills:
            result = await self.skill_registry.execute_skill(
                command,
                user_id,
                args,
                message=update.message,
                groq_api_key=getattr(self, "_groq_api_key", ""),
            )
            if result.error:
                response_text = f"❌ {result.error}"
                await update.message.reply_text(response_text)
            elif result.file_path:
                from pathlib import Path

                fp = Path(result.file_path)
                caption = result.text or ""
                response_text = caption
                ext = fp.suffix.lower()
                try:
                    with open(fp, "rb") as f:
                        if ext in (".mp4", ".webm", ".mkv", ".avi", ".mov"):
                            await update.message.reply_video(
                                video=f, caption=caption, read_timeout=120, write_timeout=120
                            )
                        elif ext in (".mp3", ".ogg", ".m4a", ".wav", ".flac", ".opus"):
                            await update.message.reply_audio(
                                audio=f, caption=caption, read_timeout=120, write_timeout=120
                            )
                        else:
                            await update.message.reply_document(
                                document=f, caption=caption, read_timeout=120, write_timeout=120
                            )
                except Exception as e:
                    logger.error(f"Failed to send file {fp}: {e}")
                    await update.message.reply_text(f"{caption}\n\n⚠️ File send failed: {e}")
                finally:
                    # Clean up temp file
                    try:
                        fp.unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                response_text = result.text or "✅ Done"
                await update.message.reply_text(response_text)
        else:
            response_text = await self.command_router.route(command, user_id, args)
            await update.message.reply_text(response_text)

        # Record message for dashboard feed
        dashboard_state.add_message_record(
            username, f"/{command} {' '.join(args)}".strip(), response_text or ""
        )

    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle incoming text messages (non-commands).

        Args:
            update: Telegram update object
            context: Telegram context
        """
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        user_message = update.message.text
        username = update.effective_user.username or str(user_id)

        # Check authorization
        if not self.auth_manager.is_authorized(user_id):
            if self.audit_logger:
                self.audit_logger.log_auth_attempt(user_id, False, "not in allowlist")

            self.auth_manager.record_failed_attempt(user_id)
            await update.message.reply_text("You are not authorized to use this bot.")
            return

        # Update dashboard stats
        dashboard_state.total_messages += 1
        dashboard_state.active_users.add(user_id)
        dashboard_state.add_activity("message", f"@{username}: {user_message[:50]}...", "💬")

        # Get conversation context
        history = self.context_store.get_context(user_id)

        # Build messages for LLM
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant."},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Add user message to context
        self.context_store.add_message(user_id, "user", user_message)

        # Send typing indicator
        await update.message.chat.send_action("typing")

        try:
            # Stream response
            response_text = await self._stream_response(update, messages, user_id)

            # Add assistant response to context
            if response_text:
                self.context_store.add_message(user_id, "assistant", response_text)
                # Update token count (rough estimate)
                dashboard_state.total_tokens += len(response_text.split()) * 2
                # Update rate limit stats
                self._update_rate_limit_stats()
                # Record message for dashboard feed
                dashboard_state.add_message_record(username, user_message, response_text)

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            dashboard_state.add_activity("error", f"Error: {str(e)[:50]}", "❌")
            await update.message.reply_text(f"Error: All providers failed. Last error: {e}")

    async def _stream_response(
        self,
        update: Update,
        messages: list[dict[str, str]],
        user_id: int,
    ) -> str:
        """Stream LLM response to Telegram.

        Args:
            update: Telegram update object
            messages: Messages for LLM
            user_id: User ID for provider selection

        Returns:
            Complete response text
        """
        # Send initial message
        sent_message = await update.message.reply_text("...")

        full_response = ""
        last_update_len = 0
        last_update_time = asyncio.get_event_loop().time()

        try:
            async for chunk in self.provider_manager.stream_with_failover(messages, user_id):
                full_response += chunk

                # Check if we should update the message
                current_time = asyncio.get_event_loop().time()
                chars_since_update = len(full_response) - last_update_len
                time_since_update = (current_time - last_update_time) * 1000

                should_update = (
                    chars_since_update >= self.streaming_min_chars
                    or time_since_update >= self.streaming_interval_ms
                )

                # Telegram message limit is 4096 chars - truncate if needed
                display_text = full_response[:4000] if len(full_response) > 4000 else full_response

                if should_update and display_text.strip():
                    try:
                        await sent_message.edit_text(display_text)
                        last_update_len = len(full_response)
                        last_update_time = current_time
                    except Exception:
                        # Ignore edit errors (e.g., message unchanged, flood control)
                        pass

            # Final update with complete response (truncated if needed)
            if full_response.strip():
                try:
                    if len(full_response) > 4000:
                        await sent_message.edit_text(
                            full_response[:4000] + "\n\n[Message truncated...]"
                        )
                    else:
                        await sent_message.edit_text(full_response)
                except Exception:
                    pass  # Ignore "message not modified" errors
            else:
                await sent_message.edit_text("(No response generated)")

        except Exception as e:
            err_msg = str(e)
            # Don't treat "message not modified" as a real error
            if "message is not modified" in err_msg.lower():
                return full_response
            logger.error(f"Streaming error: {e}")

            # Show partial response if available
            if full_response.strip():
                truncated = full_response[:3900] if len(full_response) > 3900 else full_response
                try:
                    await sent_message.edit_text(f"{truncated}\n\n⚠️ Response interrupted: {e}")
                except Exception:
                    pass
            else:
                try:
                    await sent_message.edit_text(f"Error: {e}")
                except Exception:
                    pass

        return full_response
