"""Translate skill — translate text using LibreTranslate API."""

import httpx

from src.skills.base_skill import BaseSkill, SkillResult

# Common language codes for quick reference
LANG_ALIASES = {
    "en": "en", "english": "en",
    "es": "es", "spanish": "es",
    "fr": "fr", "french": "fr",
    "de": "de", "german": "de",
    "it": "it", "italian": "it",
    "pt": "pt", "portuguese": "pt",
    "ru": "ru", "russian": "ru",
    "zh": "zh", "chinese": "zh",
    "ja": "ja", "japanese": "ja",
    "ko": "ko", "korean": "ko",
    "ar": "ar", "arabic": "ar",
    "hi": "hi", "hindi": "hi",
    "tr": "tr", "turkish": "tr",
    "nl": "nl", "dutch": "nl",
    "pl": "pl", "polish": "pl",
    "sv": "sv", "swedish": "sv",
}


class TranslateSkill(BaseSkill):
    """Translate text between languages using LibreTranslate."""

    name = "translate"
    command = "translate"
    description = "Translate text between languages"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        if len(args) < 2:
            return SkillResult(
                error="Usage: /translate <target_lang> <text>\n"
                      "Example: /translate es Hello, how are you?\n"
                      "Languages: en, es, fr, de, it, pt, ru, zh, ja, ko, ar, hi"
            )

        target_raw = args[0].lower()
        target = LANG_ALIASES.get(target_raw, target_raw)
        text = " ".join(args[1:])

        api_base = self.config.get("api_base_url", "https://libretranslate.com")
        url = f"{api_base}/translate"

        payload = {
            "q": text,
            "source": "auto",
            "target": target,
            "format": "text",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"User-Agent": "OpenClaw-Bot"},
                )
                resp.raise_for_status()
                data = resp.json()

            translated = data.get("translatedText", "")
            detected_lang = data.get("detectedLanguage", {}).get("language", "auto")

            if not translated:
                return SkillResult(error="Translation returned empty result")

            lines = [
                f"🌐 {detected_lang} → {target}",
                f"📝 {translated}",
            ]
            return SkillResult(text="\n".join(lines))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return SkillResult(error="Translation API rate limited. Try again later.")
            return SkillResult(error=f"Translation API error: {e.response.status_code}")
        except Exception as e:
            return SkillResult(error=f"Translation failed: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        try:
            import httpx  # noqa: F811
            return True
        except ImportError:
            return False
