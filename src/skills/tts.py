"""Text-to-Speech skill — convert text to audio using Microsoft Edge TTS.

Free, high-quality TTS with 300+ voices. No API key required.
Falls back to Groq Orpheus if configured and Edge TTS fails.
"""

import importlib.util
import logging
import os
import tempfile

from src.skills.base_skill import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

# Curated voice presets (Edge TTS short names)
VOICES = {
    "guy": ("en-US-GuyNeural", "Guy (male, US default)"),
    "jenny": ("en-US-JennyNeural", "Jenny (female, US)"),
    "aria": ("en-US-AriaNeural", "Aria (female, US)"),
    "davis": ("en-US-DavisNeural", "Davis (male, US)"),
    "ryan": ("en-GB-RyanNeural", "Ryan (male, British)"),
    "sonia": ("en-GB-SoniaNeural", "Sonia (female, British)"),
    "natasha": ("en-AU-NatashaNeural", "Natasha (female, Australian)"),
    "william": ("en-AU-WilliamNeural", "William (male, Australian)"),
    "neerja": ("en-IN-NeerjaNeural", "Neerja (female, Indian)"),
    "connor": ("en-IE-ConnorNeural", "Connor (male, Irish)"),
    "clara": ("en-CA-ClaraNeural", "Clara (female, Canadian)"),
}

# Groq Orpheus voices (used when engine=groq)
GROQ_VOICES = {
    "troy": "Troy (male, default)",
    "tara": "Tara (female)",
    "leah": "Leah (female)",
    "leo": "Leo (male)",
    "jess": "Jess (female)",
    "mia": "Mia (female)",
}


class TTSSkill(BaseSkill):
    """Convert text to speech using Edge TTS (free) or Groq Orpheus."""

    name = "tts"
    command = "tts"
    description = "Convert text to speech audio"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        text = " ".join(args).strip()
        if not text:
            voice_list = "\n".join(f"  • {k} — {v[1]}" for k, v in VOICES.items())
            return SkillResult(
                error=(
                    "🎙️ Usage: /tts [voice:name] <text>\n\n"
                    f"Voices:\n{voice_list}\n\n"
                    "Examples:\n"
                    "  /tts Hello world!\n"
                    "  /tts voice:ryan Good morning!\n"
                    "  /tts voice:sonia The weather is lovely today"
                )
            )

        # Parse optional voice:name prefix
        default_voice = self.config.get("default_voice", "guy")
        voice_key = default_voice
        if text.lower().startswith("voice:"):
            parts = text.split(None, 1)
            voice_arg = parts[0].split(":", 1)[1].lower()
            if voice_arg in VOICES or voice_arg in GROQ_VOICES:
                voice_key = voice_arg
                text = parts[1] if len(parts) > 1 else ""
            else:
                all_voices = list(VOICES.keys()) + list(GROQ_VOICES.keys())
                return SkillResult(
                    error=f"Unknown voice: {voice_arg}\nAvailable: {', '.join(all_voices)}"
                )

        if not text:
            return SkillResult(error="No text provided after voice selection.")

        if len(text) > 4000:
            return SkillResult(error=f"Text too long ({len(text)} chars). Max 4000.")

        tmp_dir = self.config.get("temp_dir", "/tmp/openclaw_tts")
        os.makedirs(tmp_dir, exist_ok=True)

        # If voice is a Groq voice, try Groq first
        if voice_key in GROQ_VOICES:
            result = await self._try_groq(text, voice_key, tmp_dir, kwargs)
            if result:
                return result
            # Fall through to Edge TTS with default voice
            voice_key = default_voice if default_voice in VOICES else "guy"

        # Edge TTS (primary — free, no key needed)
        return await self._edge_tts(text, voice_key, tmp_dir)

    async def _edge_tts(self, text: str, voice_key: str, tmp_dir: str) -> SkillResult:
        """Generate speech using Microsoft Edge TTS."""
        try:
            import edge_tts

            voice_id, voice_desc = VOICES.get(voice_key, VOICES["guy"])

            tmp_file = tempfile.NamedTemporaryFile(
                suffix=".mp3", dir=tmp_dir, delete=False
            )
            tmp_file.close()

            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(tmp_file.name)

            file_size = os.path.getsize(tmp_file.name)
            if file_size < 100:
                os.unlink(tmp_file.name)
                return SkillResult(error="TTS generated empty audio. Try different text.")

            return SkillResult(
                file_path=tmp_file.name,
                text=f"🎙️ {voice_desc} | {len(text)} chars",
            )

        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            # Clean up
            try:
                if os.path.exists(tmp_file.name):
                    os.unlink(tmp_file.name)
            except Exception:
                pass
            return SkillResult(error=f"TTS generation failed: {e}")

    async def _try_groq(self, text: str, voice: str, tmp_dir: str, kwargs: dict) -> SkillResult | None:
        """Try Groq Orpheus TTS. Returns None if unavailable/fails."""
        api_key = kwargs.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None

        if not importlib.util.find_spec("groq"):
            return None

        model = self.config.get("groq_model", "canopylabs/orpheus-v1-english")

        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            response = client.audio.speech.create(
                model=model, voice=voice, input=text, response_format="wav",
            )

            tmp_file = tempfile.NamedTemporaryFile(
                suffix=".wav", dir=tmp_dir, delete=False
            )
            response.write_to_file(tmp_file.name)
            tmp_file.close()

            return SkillResult(
                file_path=tmp_file.name,
                text=f"🎙️ Orpheus {voice} | {len(text)} chars",
            )

        except Exception as e:
            err_str = str(e)
            logger.warning(f"Groq TTS failed (falling back to Edge): {err_str}")
            # Don't return error — let caller fall back to Edge TTS
            return None

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("edge_tts") is not None
