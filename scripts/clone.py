#!/usr/bin/env python3
"""Clone script for OpenClaw Telegram Bot.

Exports configuration files (excluding secrets) to a portable tar.gz archive
for deploying the bot on another system. The archive includes:
- Configuration files (config.yaml, permissions.yaml, providers.yaml, skills.yaml)
- Source code (src/)
- Project files (pyproject.toml, install.py, README.md)
- A fresh .env.template requiring the target system to provide its own API keys

The archive NEVER contains .env files or any files with API keys/tokens.
"""

import argparse
import io
import os
import re
import sys
import tarfile
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple


# Patterns that match real secret values (not placeholders)
SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq API key pattern
    re.compile(r"\d{10}:[A-Za-z0-9_-]{35}"),  # Telegram bot token pattern
]

# Placeholder values that should NOT be flagged as secrets
PLACEHOLDER_SUFFIXES = {"_here", "_token_here", "_key_here", "your_", ""}
PLACEHOLDER_PATTERN = re.compile(
    r"(?:your_\w+_here|your_\w+|placeholder|example|changeme|\bx{3,}\b)",
    re.IGNORECASE,
)

# Files that are always excluded (by name)
EXCLUDED_FILENAMES: Set[str] = {
    ".env",
}

# Directory names to always exclude
EXCLUDED_DIRS: Set[str] = {
    ".venv",
    "__pycache__",
    ".git",
    ".hypothesis",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "logs",
    "data",
}

# Config files to include (relative to project root)
CONFIG_FILES: List[str] = [
    "config/config.yaml",
    "config/permissions.yaml",
    "config/providers.yaml",
    "config/skills.yaml",
]

# Top-level project files to include
PROJECT_FILES: List[str] = [
    "pyproject.toml",
    "install.py",
    "README.md",
    "LICENSE",
    "start",
    "openclaw",
]

# Directories to include (recursively)
SOURCE_DIRS: List[str] = [
    "src",
    "tests",
    "scripts",
    "assets",
]

# Default .env.template content
ENV_TEMPLATE_CONTENT = """\
# OpenClaw Telegram Bot - Environment Configuration
# Fill in your values below to configure the bot.

# Required: Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Required: Groq API Key from console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# Optional: Ollama Cloud URL (if using remote Ollama)
OLLAMA_CLOUD_URL=
"""


def file_contains_secrets(filepath: Path) -> bool:
    """Check if a file contains API keys, tokens, or other secrets.

    Args:
        filepath: Path to the file to check.

    Returns:
        True if the file contains secret patterns, False otherwise.
    """
    try:
        content = filepath.read_text(errors="ignore")
    except (OSError, UnicodeDecodeError):
        return False

    return content_contains_secrets(content)


def content_contains_secrets(content: str) -> bool:
    """Check if string content contains API keys, tokens, or other secrets.

    Scans for known secret patterns (Groq API keys, Telegram tokens) while
    ignoring placeholder/template values.

    Args:
        content: Text content to scan.

    Returns:
        True if the content contains secret patterns, False otherwise.
    """
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            matched_text = match.group(0)
            # Skip if the match is inside a placeholder context
            if not PLACEHOLDER_PATTERN.search(matched_text):
                return True
    return False


def should_exclude_path(rel_path: Path) -> bool:
    """Determine if a path should be excluded from the archive.

    Args:
        rel_path: Path relative to the project root.

    Returns:
        True if the path should be excluded.
    """
    # Check if any path component is an excluded directory
    for part in rel_path.parts:
        if part in EXCLUDED_DIRS:
            return True

    # Check if the filename is excluded
    if rel_path.name in EXCLUDED_FILENAMES:
        return True

    return False


def collect_files(project_dir: Path) -> List[Tuple[Path, str]]:
    """Collect all files to include in the archive.

    Args:
        project_dir: Root directory of the project.

    Returns:
        List of (absolute_path, archive_name) tuples.
    """
    files: List[Tuple[Path, str]] = []

    # Add config files
    for config_file in CONFIG_FILES:
        filepath = project_dir / config_file
        if filepath.exists() and filepath.is_file():
            files.append((filepath, config_file))

    # Add top-level project files
    for project_file in PROJECT_FILES:
        filepath = project_dir / project_file
        if filepath.exists() and filepath.is_file():
            files.append((filepath, project_file))

    # Add source directories recursively
    for source_dir in SOURCE_DIRS:
        dir_path = project_dir / source_dir
        if not dir_path.exists() or not dir_path.is_dir():
            continue

        for filepath in sorted(dir_path.rglob("*")):
            if not filepath.is_file():
                continue

            rel_path = filepath.relative_to(project_dir)

            if should_exclude_path(rel_path):
                continue

            files.append((filepath, str(rel_path)))

    return files


def validate_no_secrets(archive_path: Path) -> List[str]:
    """Validate that a tar.gz archive contains no secrets.

    Opens the archive and scans every text file for secret patterns.

    Args:
        archive_path: Path to the tar.gz archive.

    Returns:
        List of filenames that contain secrets (empty if clean).
    """
    violations: List[str] = []

    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            # Check filename
            name = Path(member.name).name
            if name in EXCLUDED_FILENAMES:
                violations.append(f"{member.name} (excluded filename)")
                continue

            # Check content for text files
            f = tar.extractfile(member)
            if f is None:
                continue

            try:
                content = f.read().decode("utf-8", errors="ignore")
                if content_contains_secrets(content):
                    violations.append(f"{member.name} (contains secret patterns)")
            finally:
                f.close()

    return violations


class CloneExporter:
    """Exports OpenClaw project to a portable archive excluding secrets."""

    def __init__(self, project_dir: Optional[str] = None):
        """Initialize the exporter.

        Args:
            project_dir: Path to the project root. Defaults to parent of scripts/.
        """
        if project_dir is None:
            # Default: assume this script is in <project>/scripts/
            self.project_dir = Path(__file__).parent.parent.resolve()
        else:
            self.project_dir = Path(project_dir).resolve()

    def export(self, output_path: Optional[str] = None) -> Path:
        """Create the clone archive.

        Args:
            output_path: Path for the output tar.gz file.
                         Defaults to openclaw-clone-<timestamp>.tar.gz in project dir.

        Returns:
            Path to the created archive.

        Raises:
            RuntimeError: If the archive fails secret validation.
        """
        if output_path is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            output_path = str(
                self.project_dir / f"openclaw-clone-{timestamp}.tar.gz"
            )

        archive_path = Path(output_path).resolve()
        archive_name = "openclaw"

        print(f"📦 Creating clone archive: {archive_path.name}")
        print(f"   Source: {self.project_dir}")
        print()

        # Collect files
        files = collect_files(self.project_dir)

        included: List[str] = []
        excluded: List[str] = []

        with tarfile.open(str(archive_path), "w:gz") as tar:
            # Add collected files (filtering out secrets)
            for filepath, arcname in files:
                full_arcname = f"{archive_name}/{arcname}"

                # Skip the clone script's own output
                if filepath == archive_path:
                    continue

                # Check for secrets in file content
                if file_contains_secrets(filepath):
                    excluded.append(f"{arcname} (contains secrets)")
                    continue

                tar.add(str(filepath), arcname=full_arcname)
                included.append(arcname)

            # Generate and add .env.template
            env_template_info = tarfile.TarInfo(
                name=f"{archive_name}/config/.env.template"
            )
            env_template_bytes = ENV_TEMPLATE_CONTENT.encode("utf-8")
            env_template_info.size = len(env_template_bytes)
            env_template_info.mtime = int(time.time())
            tar.addfile(env_template_info, io.BytesIO(env_template_bytes))
            included.append("config/.env.template (generated)")

        # Validate the archive
        print("🔍 Validating archive for secrets...")
        violations = validate_no_secrets(archive_path)

        if violations:
            # Remove the tainted archive
            archive_path.unlink(missing_ok=True)
            violation_list = "\n  ".join(violations)
            raise RuntimeError(
                f"Archive validation failed! Files with secrets found:\n  {violation_list}"
            )

        print("✅ Archive validated - no secrets detected")
        print()

        # Print summary
        print("📋 Included files:")
        for name in sorted(included):
            print(f"   ✓ {name}")

        if excluded:
            print()
            print("🚫 Excluded files:")
            for name in sorted(excluded):
                print(f"   ✗ {name}")

        print()
        print(f"✅ Clone archive created: {archive_path}")
        print(f"   Size: {archive_path.stat().st_size / 1024:.1f} KB")
        print()
        print("📝 To deploy on a new system:")
        print(f"   1. Copy {archive_path.name} to the target machine")
        print(f"   2. tar xzf {archive_path.name}")
        print("   3. cd openclaw")
        print("   4. cp config/.env.template config/.env")
        print("   5. Edit config/.env with your API keys")
        print("   6. python3 install.py")

        return archive_path


def main() -> int:
    """CLI entry point for the clone script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Export OpenClaw configuration to a portable archive (excluding secrets)."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path for the tar.gz archive (default: openclaw-clone-<timestamp>.tar.gz)",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project root directory (default: auto-detect from script location)",
    )

    args = parser.parse_args()

    try:
        exporter = CloneExporter(project_dir=args.project_dir)
        exporter.export(output_path=args.output)
        return 0
    except RuntimeError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
