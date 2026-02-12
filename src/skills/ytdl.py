"""YouTube download skill — download audio/video via yt-dlp with auto-update."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from src.skills.base_skill import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

# Auto-update tracking
_last_update_check: float = 0
_UPDATE_INTERVAL = 86400  # Check once per day


def _auto_update_ytdlp() -> None:
    """Update yt-dlp if last check was more than UPDATE_INTERVAL ago."""
    global _last_update_check
    import time

    now = time.time()
    if now - _last_update_check < _UPDATE_INTERVAL:
        return

    _last_update_check = now
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("yt-dlp auto-updated successfully")
        else:
            logger.warning(f"yt-dlp auto-update failed: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"yt-dlp auto-update error: {e}")


class YtdlSkill(BaseSkill):
    """Download audio or video from YouTube and other sites via yt-dlp."""

    name = "ytdl"
    command = "ytdl"
    description = "Download audio/video from YouTube"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        # Runtime dependency check for ffmpeg/ffprobe
        missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
        if missing:
            return SkillResult(
                error=f"Missing required system dependencies: {', '.join(missing)}. "
                "Install with: apt-get install ffmpeg"
            )

        if not args:
            return SkillResult(
                error="Usage: /ytdl <url> [audio|video]\n"
                "Example: /ytdl https://youtube.com/watch?v=... audio"
            )

        # Parse args: URL is first, optional format is second
        url = args[0]
        fmt = args[1].lower() if len(args) > 1 else self.config.get("default_format", "video")

        if fmt not in ("audio", "video"):
            return SkillResult(error="Format must be 'audio' or 'video'")

        max_size_mb = self.config.get("max_file_size_mb", 50)
        temp_dir = self.config.get("temp_dir", "/tmp/openclaw_ytdl")
        os.makedirs(temp_dir, exist_ok=True)
        # Clean old files to avoid picking up stale downloads
        for old_file in Path(temp_dir).iterdir():
            if old_file.is_file():
                try:
                    old_file.unlink()
                except OSError:
                    pass

        # Auto-update yt-dlp in background
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _auto_update_ytdlp)

        # Build yt-dlp command
        output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")

        cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings"]

        if fmt == "audio":
            cmd += [
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "5",
                "-o",
                output_template,
                "--max-filesize",
                f"{max_size_mb}M",
                url,
            ]
        else:
            cmd += [
                "-f",
                "best[ext=mp4][filesize<50M]/best[ext=mp4]/best",
                "--merge-output-format",
                "mp4",
                "-o",
                output_template,
                "--max-filesize",
                f"{max_size_mb}M",
                url,
            ]

        try:
            # Get info first for the title
            info_cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--no-playlist",
                "--print",
                "%(title)s",
                "--print",
                "%(duration)s",
                url,
            ]
            info_result = await asyncio.to_thread(
                subprocess.run,
                info_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            title = "Unknown"
            duration = "?"
            if info_result.returncode == 0:
                info_lines = info_result.stdout.strip().split("\n")
                if len(info_lines) >= 1:
                    title = info_lines[0][:100]
                if len(info_lines) >= 2:
                    try:
                        secs = int(float(info_lines[1]))
                        duration = f"{secs // 60}:{secs % 60:02d}"
                    except (ValueError, TypeError):
                        pass

            # Download
            dl_result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if dl_result.returncode != 0:
                err = dl_result.stderr[:300] if dl_result.stderr else "Unknown error"
                return SkillResult(error=f"Download failed: {err}")

            # Find the downloaded file
            downloaded = self._find_latest_file(temp_dir)
            if not downloaded:
                return SkillResult(error="Download completed but file not found")

            # Check file size
            size_mb = downloaded.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                downloaded.unlink(missing_ok=True)
                return SkillResult(
                    error=f"File too large ({size_mb:.1f}MB > {max_size_mb}MB limit)"
                )

            return SkillResult(
                text=f"🎵 {title} ({duration})\n📁 {size_mb:.1f}MB",
                file_path=str(downloaded),
            )

        except subprocess.TimeoutExpired:
            return SkillResult(error="⏱️ Download timed out (120s limit)")
        except Exception as e:
            return SkillResult(error=f"Download error: {e}")

    def _find_latest_file(self, directory: str) -> Path | None:
        """Find the most recently modified file in the temp directory."""
        temp_dir = Path(directory)
        files = [f for f in temp_dir.iterdir() if f.is_file()]
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)

    @classmethod
    def check_dependencies(cls) -> bool:
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            return False
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            return False
        return True
