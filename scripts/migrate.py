#!/usr/bin/env python3
"""Migration script for OpenClaw Telegram Bot.

Provides backup and restore functionality for complete system state:
- Configuration files (config.yaml, permissions.yaml, providers.yaml, skills.yaml)
- Conversation history (data/contexts.json)
- Usage statistics (data/usage_stats.json)
- Audit logs (logs/)
- Manifest with SHA-256 checksums for integrity validation

The backup NEVER includes .env files (secrets). A .env.template is generated instead.

Usage:
    python scripts/migrate.py --backup [--output path/to/backup.tar.gz]
    python scripts/migrate.py --restore path/to/backup.tar.gz [--skip-logs]
"""

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Files to back up (relative to project root)
CONFIG_FILES: List[str] = [
    "config/config.yaml",
    "config/permissions.yaml",
    "config/providers.yaml",
    "config/skills.yaml",
]

DATA_FILES: List[str] = [
    "data/contexts.json",
    "data/usage_stats.json",
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


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest for the given bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest for a file on disk.

    Args:
        filepath: Path to the file.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    return compute_sha256(filepath.read_bytes())


class MigrationManager:
    """Manages backup and restore operations for the OpenClaw bot."""

    def __init__(self, project_dir: Optional[str] = None):
        """Initialize the migration manager.

        Args:
            project_dir: Path to the project root. Defaults to parent of scripts/.
        """
        if project_dir is None:
            self.project_dir = Path(__file__).parent.parent.resolve()
        else:
            self.project_dir = Path(project_dir).resolve()

    def backup(self, output_path: Optional[str] = None) -> Path:
        """Create a complete backup archive.

        Backs up configuration files, conversation data, usage statistics,
        and audit logs. Generates a manifest.json with SHA-256 checksums
        for integrity validation. Never includes .env (secrets).

        Args:
            output_path: Path for the output tar.gz file.
                         Defaults to openclaw-backup-<timestamp>.tar.gz.

        Returns:
            Path to the created backup archive.
        """
        if output_path is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            output_path = str(
                self.project_dir / f"openclaw-backup-{timestamp}.tar.gz"
            )

        archive_path = Path(output_path).resolve()
        archive_prefix = "openclaw-backup"

        print(f"📦 Creating backup archive: {archive_path.name}")
        print(f"   Source: {self.project_dir}")
        print()

        manifest: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "version": self._get_version(),
            "files": {},
        }

        included: List[str] = []

        with tarfile.open(str(archive_path), "w:gz") as tar:
            # Back up config files
            for rel_path in CONFIG_FILES:
                filepath = self.project_dir / rel_path
                if filepath.exists() and filepath.is_file():
                    self._add_file_to_tar(
                        tar, filepath, f"{archive_prefix}/{rel_path}", manifest
                    )
                    included.append(rel_path)

            # Back up data files
            for rel_path in DATA_FILES:
                filepath = self.project_dir / rel_path
                if filepath.exists() and filepath.is_file():
                    self._add_file_to_tar(
                        tar, filepath, f"{archive_prefix}/{rel_path}", manifest
                    )
                    included.append(rel_path)

            # Back up log files
            logs_dir = self.project_dir / "logs"
            if logs_dir.exists() and logs_dir.is_dir():
                for log_file in sorted(logs_dir.rglob("*")):
                    if log_file.is_file():
                        rel = log_file.relative_to(self.project_dir)
                        self._add_file_to_tar(
                            tar, log_file, f"{archive_prefix}/{rel}", manifest
                        )
                        included.append(str(rel))

            # Generate .env.template (never include actual .env)
            template_bytes = ENV_TEMPLATE_CONTENT.encode("utf-8")
            template_arcname = f"{archive_prefix}/config/.env.template"
            info = tarfile.TarInfo(name=template_arcname)
            info.size = len(template_bytes)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(template_bytes))
            manifest["files"]["config/.env.template"] = compute_sha256(template_bytes)
            included.append("config/.env.template (generated)")

            # Write manifest.json into the archive
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            manifest_info = tarfile.TarInfo(
                name=f"{archive_prefix}/manifest.json"
            )
            manifest_info.size = len(manifest_bytes)
            manifest_info.mtime = int(time.time())
            tar.addfile(manifest_info, io.BytesIO(manifest_bytes))
            included.append("manifest.json")

        # Print summary
        print("📋 Backed up files:")
        for name in sorted(included):
            print(f"   ✓ {name}")

        print()
        print(f"✅ Backup created: {archive_path}")
        print(f"   Size: {archive_path.stat().st_size / 1024:.1f} KB")

        return archive_path

    def restore(
        self, archive_path: str, skip_logs: bool = False
    ) -> Dict[str, Any]:
        """Restore from a backup archive.

        Validates archive integrity using manifest checksums, then extracts
        configuration files, conversation data, usage statistics, and
        optionally logs.

        Args:
            archive_path: Path to the backup tar.gz archive.
            skip_logs: If True, skip restoring log files.

        Returns:
            Dict with restore results:
                - restored: list of restored file paths
                - skipped: list of skipped file paths
                - errors: list of error messages

        Raises:
            FileNotFoundError: If the archive does not exist.
            ValueError: If the archive has no manifest or integrity check fails.
        """
        archive = Path(archive_path).resolve()
        if not archive.exists():
            raise FileNotFoundError(f"Backup archive not found: {archive}")

        print(f"📦 Restoring from: {archive.name}")
        print(f"   Target: {self.project_dir}")
        print()

        # Read manifest from archive
        manifest = self._read_manifest(archive)

        print(f"   Backup timestamp: {manifest.get('timestamp', 'unknown')}")
        print(f"   Backup version: {manifest.get('version', 'unknown')}")
        print()

        # Validate integrity
        print("🔍 Validating archive integrity...")
        violations = self.validate_integrity(archive, manifest)
        if violations:
            violation_list = "\n  ".join(violations)
            raise ValueError(
                f"Integrity validation failed:\n  {violation_list}"
            )
        print("✅ Integrity check passed")
        print()

        # Extract files
        restored: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        with tarfile.open(str(archive), "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue

                # Strip the archive prefix to get relative path
                rel_path = self._strip_prefix(member.name)
                if rel_path is None:
                    continue

                # Skip manifest itself
                if rel_path == "manifest.json":
                    continue

                # Skip logs if requested
                if skip_logs and rel_path.startswith("logs/"):
                    skipped.append(rel_path)
                    continue

                # Extract to project directory
                target = self.project_dir / rel_path
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f = tar.extractfile(member)
                    if f is not None:
                        target.write_bytes(f.read())
                        restored.append(rel_path)
                except Exception as e:
                    errors.append(f"{rel_path}: {e}")

        # Print summary
        print("📋 Restore results:")
        for name in sorted(restored):
            print(f"   ✓ {name}")
        if skipped:
            print()
            print("⏭️  Skipped:")
            for name in sorted(skipped):
                print(f"   - {name}")
        if errors:
            print()
            print("❌ Errors:")
            for err in errors:
                print(f"   ! {err}")

        print()
        print(f"✅ Restore complete: {len(restored)} files restored")

        return {
            "restored": restored,
            "skipped": skipped,
            "errors": errors,
        }

    def validate_integrity(
        self, archive_path: Path, manifest: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Validate archive integrity against manifest checksums.

        Args:
            archive_path: Path to the backup tar.gz archive.
            manifest: Pre-loaded manifest dict. If None, reads from archive.

        Returns:
            List of integrity violation messages (empty if all OK).
        """
        archive = Path(archive_path).resolve()

        if manifest is None:
            manifest = self._read_manifest(archive)

        file_checksums: Dict[str, str] = manifest.get("files", {})
        violations: List[str] = []

        with tarfile.open(str(archive), "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue

                rel_path = self._strip_prefix(member.name)
                if rel_path is None or rel_path == "manifest.json":
                    continue

                if rel_path not in file_checksums:
                    violations.append(
                        f"{rel_path}: not listed in manifest"
                    )
                    continue

                f = tar.extractfile(member)
                if f is None:
                    violations.append(f"{rel_path}: could not read from archive")
                    continue

                actual = compute_sha256(f.read())
                expected = file_checksums[rel_path]
                if actual != expected:
                    violations.append(
                        f"{rel_path}: checksum mismatch "
                        f"(expected {expected[:12]}..., got {actual[:12]}...)"
                    )

        return violations

    def _add_file_to_tar(
        self,
        tar: tarfile.TarFile,
        filepath: Path,
        arcname: str,
        manifest: Dict[str, Any],
    ) -> None:
        """Add a file to the tar archive and record its checksum in the manifest.

        Args:
            tar: Open TarFile to add to.
            filepath: Absolute path to the file on disk.
            arcname: Name to use inside the archive.
            manifest: Manifest dict to update with checksum.
        """
        data = filepath.read_bytes()
        checksum = compute_sha256(data)

        info = tarfile.TarInfo(name=arcname)
        info.size = len(data)
        info.mtime = int(filepath.stat().st_mtime)
        tar.addfile(info, io.BytesIO(data))

        # Store relative path (strip archive prefix) as key
        rel_path = self._strip_prefix(arcname)
        if rel_path:
            manifest["files"][rel_path] = checksum

    def _read_manifest(self, archive_path: Path) -> Dict[str, Any]:
        """Read manifest.json from a backup archive.

        Args:
            archive_path: Path to the tar.gz archive.

        Returns:
            Parsed manifest dict.

        Raises:
            ValueError: If no manifest.json found in the archive.
        """
        with tarfile.open(str(archive_path), "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("manifest.json") and member.isfile():
                    f = tar.extractfile(member)
                    if f is not None:
                        return json.loads(f.read().decode("utf-8"))

        raise ValueError("No manifest.json found in backup archive")

    def _strip_prefix(self, arcname: str) -> Optional[str]:
        """Strip the archive prefix from a member name.

        Args:
            arcname: Full archive member name (e.g. 'openclaw-backup/config/config.yaml').

        Returns:
            Relative path without prefix, or None if invalid.
        """
        parts = arcname.split("/", 1)
        if len(parts) < 2:
            return None
        return parts[1]

    def _get_version(self) -> str:
        """Read the project version from pyproject.toml.

        Returns:
            Version string, or 'unknown' if not found.
        """
        pyproject = self.project_dir / "pyproject.toml"
        if not pyproject.exists():
            return "unknown"

        try:
            content = pyproject.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("version"):
                    # Parse version = "x.y.z"
                    _, _, value = line.partition("=")
                    return value.strip().strip('"').strip("'")
        except Exception:
            pass

        return "unknown"


def main() -> int:
    """CLI entry point for the migration script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Backup and restore OpenClaw bot state."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--backup",
        action="store_true",
        help="Create a complete backup archive",
    )
    group.add_argument(
        "--restore",
        type=str,
        metavar="ARCHIVE",
        help="Restore from a backup archive",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path for backup archive (only with --backup)",
    )
    parser.add_argument(
        "--skip-logs",
        action="store_true",
        help="Skip restoring log files (only with --restore)",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project root directory (default: auto-detect)",
    )

    args = parser.parse_args()

    try:
        manager = MigrationManager(project_dir=args.project_dir)

        if args.backup:
            manager.backup(output_path=args.output)
            return 0
        elif args.restore:
            result = manager.restore(
                archive_path=args.restore, skip_logs=args.skip_logs
            )
            if result["errors"]:
                return 1
            return 0
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"❌ Validation error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
