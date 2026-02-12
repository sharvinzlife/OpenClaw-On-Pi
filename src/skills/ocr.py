"""OCR skill — extract text from images using Tesseract."""

import os
import shutil
import tempfile
from pathlib import Path

from src.skills.base_skill import BaseSkill, SkillResult


class OcrSkill(BaseSkill):
    """Extract text from images using Tesseract OCR."""

    name = "ocr"
    command = "ocr"
    description = "Extract text from images (reply to an image with /ocr)"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        import pytesseract
        from PIL import Image

        # The image_path should be passed via kwargs by the TelegramHandler
        image_path = kwargs.get("image_path")

        if not image_path:
            return SkillResult(
                error="Reply to an image with /ocr to extract text.\n"
                      "Or send an image with /ocr as the caption."
            )

        temp_dir = self.config.get("temp_dir", "/tmp/openclaw_ocr")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            img = Image.open(image_path)

            # Optional language from args: /ocr eng+fra
            lang = args[0] if args else "eng"

            text = pytesseract.image_to_string(img, lang=lang).strip()

            if not text:
                return SkillResult(text="🔍 No text detected in the image.")

            # Truncate for Telegram message limit
            if len(text) > 3000:
                text = text[:2997] + "..."

            return SkillResult(text=f"📝 Extracted text:\n\n{text}")

        except Exception as e:
            return SkillResult(error=f"OCR failed: {e}")
        finally:
            # Clean up the downloaded image
            if image_path and Path(image_path).exists():
                try:
                    Path(image_path).unlink()
                except OSError:
                    pass

    @classmethod
    def check_dependencies(cls) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
            # Also check that tesseract binary is available
            if not shutil.which("tesseract"):
                return False
            return True
        except ImportError:
            return False
