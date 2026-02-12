"""Text-to-Speech skill — convert text to audio using Groq Orpheus TTS."""

import importlib.util
import logging
import os
import tempfile

from src.skills.base_skill import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

# Available voices for Orpheus English
VOICES = {
    "troy": "Troy (male, default)",
    "tara": "Tara (female)",
    "leah": "Leah (female)",
    "leo": "Leo (male)",
    "jess": "Jess (female)",
    "mia": "Mia (female)",
}

# Vocal direction tags the model supports
VOCAL_DIRECTIONS = [
    "[cheerful]",
    "[sad]",
    "[whisper]",
    "[angry]",
    "[excited]",
    "[calm]",
    "[surprised]",
    "[serious]",
    "[friendly]",
]


class TTSSkill(BaseSkill):
    """Convert text to speech using Groq's Orpheus TTS model."""

    name = "tts"
    command = "tts"
    description = "Convert text to speech audio"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        text = " ".join(args).strip()
        if not text:
            voice_list = "\n".join(f"  • {k} — {v}" for k, v in VOICES.items())
            return SkillResult(
                error=(
                    "🎙️ Usage: /tts [voice:name] <text>\n\n"
                    f"Voices:\n{voice_list}\n\n"
                    "Vocal directions: wrap in brackets\n"
                    "  e.g. /tts [cheerful] Hello world!\n"
                    "  e.g. /tts voice:tara Good morning!"
                )
            )

        # Parse optional voice:name prefix
        voice = self.config.get("default_voice", "troy")
        if text.lower().startswith("voice:"):
            parts = text.split(None, 1)
            voice_arg = parts[0].split(":", 1)[1].lower()
            if voice_arg in VOICES:
                voice = voice_arg
                text = parts[1] if len(parts) > 1 else ""
            else:
                return SkillResult(
                    error=f"Unknown voice: {voice_arg}\nAvailable: {', '.join(VOICES.keys())}"
                )

        if not text:
            return SkillResult(error="No text provided after voice selection.")

        # Max 4000 chars (Groq limit)
        if len(text) > 4000:
            return SkillResult(error=f"Text too long ({len(text)} chars). Max 4000.")

        api_key = kwargs.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return SkillResult(error="Groq API key not configured. TTS requires Groq.")

        model = self.config.get("model", "canopylabs/orpheus-v1-english")

        try:
            from groq import Groq

            client = Groq(api_key=api_key)

            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="wav",
            )

            # Save to temp file
            tmp_dir = self.config.get("temp_dir", "/tmp/openclaw_tts")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", dir=tmp_dir, delete=False)
            response.write_to_file(tmp_file.name)
            tmp_file.close()

            return SkillResult(
                file_path=tmp_file.name,
                text=f"🎙️ Voice: {voice} | {len(text)} chars",
            )

        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return SkillResult(error=f"TTS generation failed: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("groq") is not None
