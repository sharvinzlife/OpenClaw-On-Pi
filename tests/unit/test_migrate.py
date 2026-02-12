"""Unit tests for the migration script."""

import json
import tarfile
import io
from pathlib import Path

import pytest

from scripts.migrate import (
    MigrationManager,
    compute_sha256,
    compute_file_sha256,
)


class TestComputeSha256:
    """Tests for SHA-256 checksum computation."""

    def test_deterministic(self):
        data = b"hello world"
        assert compute_sha256(data) == compute_sha256(data)

    def test_different_data_different_hash(self):
        assert compute_sha256(b"hello") != compute_sha256(b"world")

    def test_empty_bytes(self):
        result = compute_sha256(b"")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest is 64 chars

    def test_file_sha256(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"test content")
        assert compute_file_sha256(f) == compute_sha256(b"test content")


def _create_project(tmp_path: Path) -> Path:
    """Create a minimal project structure for testing.

    Returns the project root path.
    """
    project = tmp_path / "project"
    project.mkdir()

    # Config files
    config_dir = project / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("bot:\n  name: test\n")
    (config_dir / "permissions.yaml").write_text("admins: [123]\n")
    (config_dir / "providers.yaml").write_text("groq:\n  enabled: true\n")
    (config_dir / "skills.yaml").write_text("skills:\n  calc:\n    enabled: true\n")
    (config_dir / ".env").write_text("GROQ_API_KEY=secret_key_value")

    # Data files
    data_dir = project / "data"
    data_dir.mkdir()
    contexts = {"12345": [{"role": "user", "content": "hello"}]}
    (data_dir / "contexts.json").write_text(json.dumps(contexts))
    usage = {"12345": {"tokens": 100}}
    (data_dir / "usage_stats.json").write_text(json.dumps(usage))

    # Log files
    logs_dir = project / "logs"
    logs_dir.mkdir()
    (logs_dir / "audit.log").write_text("2024-01-01 INFO: test log entry\n")

    # pyproject.toml for version
    (project / "pyproject.toml").write_text(
        '[project]\nname = "openclaw"\nversion = "0.2.0"\n'
    )

    return project


class TestMigrationManagerBackup:
    """Tests for backup functionality."""

    def test_backup_creates_archive(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        result = manager.backup(str(output))

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_backup_includes_config_files(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("config/config.yaml" in n for n in names)
            assert any("config/permissions.yaml" in n for n in names)
            assert any("config/providers.yaml" in n for n in names)
            assert any("config/skills.yaml" in n for n in names)

    def test_backup_includes_data_files(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("data/contexts.json" in n for n in names)
            assert any("data/usage_stats.json" in n for n in names)

    def test_backup_includes_logs(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("logs/audit.log" in n for n in names)

    def test_backup_excludes_env_file(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            # Should NOT have config/.env (only .env.template)
            env_files = [n for n in names if n.endswith(".env")]
            assert len(env_files) == 0

    def test_backup_generates_env_template(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any(".env.template" in n for n in names)

            for member in tar.getmembers():
                if ".env.template" in member.name:
                    f = tar.extractfile(member)
                    content = f.read().decode("utf-8")
                    assert "your_telegram_bot_token_here" in content
                    assert "your_groq_api_key_here" in content
                    break

    def test_backup_includes_manifest(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("manifest.json" in n for n in names)

            for member in tar.getmembers():
                if "manifest.json" in member.name:
                    f = tar.extractfile(member)
                    manifest = json.loads(f.read().decode("utf-8"))
                    assert "timestamp" in manifest
                    assert "version" in manifest
                    assert "files" in manifest
                    assert manifest["version"] == "0.2.0"
                    # Checksums should be present for backed-up files
                    assert "config/config.yaml" in manifest["files"]
                    assert "data/contexts.json" in manifest["files"]
                    break

    def test_backup_manifest_checksums_are_valid(self, tmp_path):
        project = _create_project(tmp_path)
        output = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(output))

        # Read manifest
        with tarfile.open(str(output), "r:gz") as tar:
            manifest = None
            file_contents = {}

            for member in tar.getmembers():
                if not member.isfile():
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                data = f.read()
                if "manifest.json" in member.name:
                    manifest = json.loads(data.decode("utf-8"))
                else:
                    # Strip prefix
                    parts = member.name.split("/", 1)
                    if len(parts) == 2:
                        file_contents[parts[1]] = data

            assert manifest is not None
            for rel_path, expected_hash in manifest["files"].items():
                assert rel_path in file_contents, f"{rel_path} missing from archive"
                actual_hash = compute_sha256(file_contents[rel_path])
                assert actual_hash == expected_hash, f"Checksum mismatch for {rel_path}"

    def test_backup_skips_missing_data_files(self, tmp_path):
        """Backup works even if optional data files don't exist."""
        project = tmp_path / "project"
        project.mkdir()
        config_dir = project / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("bot: {}")
        (project / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')

        output = tmp_path / "backup.tar.gz"
        manager = MigrationManager(str(project))
        result = manager.backup(str(output))

        assert result.exists()

    def test_backup_default_output_path(self, tmp_path):
        project = _create_project(tmp_path)
        manager = MigrationManager(str(project))
        result = manager.backup()

        assert result.exists()
        assert "openclaw-backup-" in result.name
        assert result.name.endswith(".tar.gz")

        # Clean up
        result.unlink()


class TestMigrationManagerRestore:
    """Tests for restore functionality."""

    def _backup_and_get_archive(self, tmp_path: Path) -> tuple:
        """Helper: create a project, back it up, return (project, archive)."""
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"
        manager = MigrationManager(str(project))
        manager.backup(str(archive))
        return project, archive

    def test_restore_config_files(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        # Create a fresh target directory
        target = tmp_path / "target"
        target.mkdir()
        (target / "config").mkdir()
        (target / "data").mkdir()

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive))

        assert "config/config.yaml" in result["restored"]
        assert (target / "config" / "config.yaml").exists()
        content = (target / "config" / "config.yaml").read_text()
        assert "bot:" in content

    def test_restore_data_files(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        target = tmp_path / "target"
        target.mkdir()

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive))

        assert "data/contexts.json" in result["restored"]
        contexts = json.loads((target / "data" / "contexts.json").read_text())
        assert "12345" in contexts

        assert "data/usage_stats.json" in result["restored"]
        usage = json.loads((target / "data" / "usage_stats.json").read_text())
        assert "12345" in usage

    def test_restore_logs(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        target = tmp_path / "target"
        target.mkdir()

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive))

        assert "logs/audit.log" in result["restored"]
        assert (target / "logs" / "audit.log").exists()

    def test_restore_skip_logs(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        target = tmp_path / "target"
        target.mkdir()

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive), skip_logs=True)

        assert "logs/audit.log" in result["skipped"]
        assert not (target / "logs" / "audit.log").exists()

    def test_restore_creates_directories(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        target = tmp_path / "target"
        target.mkdir()
        # Don't pre-create subdirectories — restore should create them

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive))

        assert (target / "config").is_dir()
        assert (target / "data").is_dir()
        assert (target / "logs").is_dir()

    def test_restore_nonexistent_archive_raises(self, tmp_path):
        manager = MigrationManager(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            manager.restore("/nonexistent/backup.tar.gz")

    def test_restore_no_errors(self, tmp_path):
        project, archive = self._backup_and_get_archive(tmp_path)

        target = tmp_path / "target"
        target.mkdir()

        manager = MigrationManager(str(target))
        result = manager.restore(str(archive))

        assert result["errors"] == []


class TestMigrationManagerIntegrity:
    """Tests for integrity validation."""

    def test_valid_archive_passes_integrity(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        violations = manager.validate_integrity(archive)
        assert violations == []

    def test_tampered_archive_fails_integrity(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        # Tamper with the archive: rebuild with modified content
        tampered = tmp_path / "tampered.tar.gz"
        with tarfile.open(str(archive), "r:gz") as src:
            with tarfile.open(str(tampered), "w:gz") as dst:
                for member in src.getmembers():
                    if not member.isfile():
                        continue
                    f = src.extractfile(member)
                    if f is None:
                        continue
                    data = f.read()

                    # Tamper with config.yaml
                    if "config/config.yaml" in member.name and "manifest" not in member.name:
                        data = b"TAMPERED CONTENT"
                        member.size = len(data)

                    dst.addfile(member, io.BytesIO(data))

        violations = manager.validate_integrity(tampered)
        assert len(violations) > 0
        assert any("config/config.yaml" in v for v in violations)

    def test_archive_without_manifest_raises(self, tmp_path):
        # Create an archive with no manifest
        archive = tmp_path / "no_manifest.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            content = b"bot: {}"
            info = tarfile.TarInfo(name="openclaw-backup/config/config.yaml")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        manager = MigrationManager(str(tmp_path))
        with pytest.raises(ValueError, match="No manifest.json"):
            manager.validate_integrity(archive)

    def test_restore_rejects_tampered_archive(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        # Tamper
        tampered = tmp_path / "tampered.tar.gz"
        with tarfile.open(str(archive), "r:gz") as src:
            with tarfile.open(str(tampered), "w:gz") as dst:
                for member in src.getmembers():
                    if not member.isfile():
                        continue
                    f = src.extractfile(member)
                    if f is None:
                        continue
                    data = f.read()
                    if "config/config.yaml" in member.name and "manifest" not in member.name:
                        data = b"TAMPERED"
                        member.size = len(data)
                    dst.addfile(member, io.BytesIO(data))

        target = tmp_path / "target"
        target.mkdir()
        restore_manager = MigrationManager(str(target))

        with pytest.raises(ValueError, match="Integrity validation failed"):
            restore_manager.restore(str(tampered))


class TestBackupRestoreRoundTrip:
    """Tests that backup → restore preserves data."""

    def test_round_trip_preserves_contexts(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        # Restore to a fresh directory
        target = tmp_path / "target"
        target.mkdir()
        restore_manager = MigrationManager(str(target))
        restore_manager.restore(str(archive))

        # Compare contexts
        original = json.loads((project / "data" / "contexts.json").read_text())
        restored = json.loads((target / "data" / "contexts.json").read_text())
        assert original == restored

    def test_round_trip_preserves_usage_stats(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        target = tmp_path / "target"
        target.mkdir()
        restore_manager = MigrationManager(str(target))
        restore_manager.restore(str(archive))

        original = json.loads((project / "data" / "usage_stats.json").read_text())
        restored = json.loads((target / "data" / "usage_stats.json").read_text())
        assert original == restored

    def test_round_trip_preserves_config(self, tmp_path):
        project = _create_project(tmp_path)
        archive = tmp_path / "backup.tar.gz"

        manager = MigrationManager(str(project))
        manager.backup(str(archive))

        target = tmp_path / "target"
        target.mkdir()
        restore_manager = MigrationManager(str(target))
        restore_manager.restore(str(archive))

        for config_file in ["config.yaml", "permissions.yaml", "providers.yaml", "skills.yaml"]:
            original = (project / "config" / config_file).read_text()
            restored = (target / "config" / config_file).read_text()
            assert original == restored, f"Mismatch in {config_file}"
