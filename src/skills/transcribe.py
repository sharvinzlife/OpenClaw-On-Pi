"""Transcription skill — convert voice/audio to text using Groq Whisper."""

import importlib.util
import logging
import os

from src.skills.base_skill import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


class TranscribeSkill(BaseSkill):
    """Transcribe voice messages and audio files using Groq Whisper."""

    name = "transcribe"
    command = "transcribe"
    description = "Transcribe voice/audio to text"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        message = kwargs.get("message")
        if not message:
            return SkillResult(error="Send a voice message or reply to one with /transcribe")

        # Check for voice message, audio, or replied-to message
        voice = getattr(message, "voice", None)
        audio = getattr(message, "audio", None)
        reply = getattr(message, "reply_to_message", None)

        target_file = voice or audio
        if not target_file and reply:
            target_file = getattr(reply, "voice", None) or getattr(reply, "audio", None)

        if not target_file:
            return SkillResult(
                error=(
                    "🎤 Usage: Send a voice message, then reply with /transcribe\n"
                    "Or forward an audio file and reply with /transcribe\n\n"
                    "Supported: voice messages, mp3, wav, ogg, flac, m4a"
                )
            )

        api_key = kwargs.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return SkillResult(error="Groq API key not configured. Transcription requires Groq.")

        model = self.config.get("model", "whisper-large-v3-turbo")
        language = " ".join(args).strip() if args else self.config.get("language", "")

        tmp_dir = self.config.get("temp_dir", "/tmp/openclaw_transcribe")
        os.makedirs(tmp_dir, exist_ok=True)

        try:
            # Download the audio file from Telegram
            file_obj = await target_file.get_file()
            ext = ".ogg"  # Telegram voice messages are ogg
            if hasattr(target_file, "file_name") and target_file.file_name:
                _, dot_ext = os.path.splitext(target_file.file_name)
                if dot_ext.lower() in SUPPORTED_FORMATS:
                    ext = dot_ext.lower()

            tmp_path = os.path.join(tmp_dir, f"transcribe_{user_id}{ext}")
            await file_obj.download_to_drive(tmp_path)

            # File size check (25MB free tier)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if file_size_mb > 25:
                os.unlink(tmp_path)
                return SkillResult(error=f"Audio too large ({file_size_mb:.1f}MB). Max 25MB.")

            # Transcribe with Groq Whisper
            from groq import Groq

            client = Groq(api_key=api_key)

            with open(tmp_path, "rb") as audio_file:
                transcription_kwargs = {
                    "file": audio_file,
                    "model": model,
                    "response_format": "verbose_json",
                    "temperature": 0.0,
                }
                if language:
                    transcription_kwargs["language"] = language

                result = client.audio.transcriptions.create(**transcription_kwargs)

            # Clean up
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            text = result.text if hasattr(result, "text") else str(result)
            if not text or not text.strip():
                return SkillResult(text="🎤 (no speech detected)")

            # Format output
            duration_str = ""
            if hasattr(result, "duration") and result.duration:
                mins, secs = divmod(int(result.duration), 60)
                duration_str = f" | ⏱️ {mins}:{secs:02d}"

            lang_str = ""
            if hasattr(result, "language") and result.language:
                lang_str = f" | 🌐 {result.language}"

            header = f"🎤 Transcription{duration_str}{lang_str}\n{'─' * 30}\n"
            return SkillResult(text=f"{header}{text}")

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            # Clean up on error
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
            return SkillResult(error=f"Transcription failed: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("groq") is not None
