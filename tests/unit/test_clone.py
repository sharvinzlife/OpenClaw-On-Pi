"""Unit tests for the clone script."""

import tarfile
import tempfile
from pathlib import Path

import pytest

from scripts.clone import (
    CloneExporter,
    collect_files,
    content_contains_secrets,
    file_contains_secrets,
    should_exclude_path,
    validate_no_secrets,
)


class TestContentContainsSecrets:
    """Tests for secret detection in content."""

    def test_detects_groq_api_key(self):
        content = "GROQ_API_KEY=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
        assert content_contains_secrets(content) is True

    def test_detects_telegram_token(self):
        content = "TELEGRAM_BOT_TOKEN=8542863735:AAHgusk4j32oS-MxuxJUOIe7QGKCzDq7h3I"
        assert content_contains_secrets(content) is True

    def test_ignores_placeholder_values(self):
        content = "GROQ_API_KEY=your_groq_api_key_here"
        assert content_contains_secrets(content) is False

    def test_ignores_template_content(self):
        content = """\
# OpenClaw Telegram Bot - Environment Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GROQ_API_KEY=your_groq_api_key_here
OLLAMA_CLOUD_URL=
"""
        assert content_contains_secrets(content) is False

    def test_clean_yaml_content(self):
        content = """\
bot:
  default_provider: groq
  default_model: llama-3.1-70b-versatile
  response_timeout: 30
"""
        assert content_contains_secrets(content) is False

    def test_clean_python_content(self):
        content = """\
class MyClass:
    def __init__(self):
        self.name = "test"
"""
        assert content_contains_secrets(content) is False

    def test_empty_content(self):
        assert content_contains_secrets("") is False


class TestShouldExcludePath:
    """Tests for path exclusion logic."""

    def test_excludes_env_file(self):
        assert should_exclude_path(Path("config/.env")) is True

    def test_excludes_venv_dir(self):
        assert should_exclude_path(Path(".venv/bin/python")) is True

    def test_excludes_pycache(self):
        assert should_exclude_path(Path("src/__pycache__/module.pyc")) is True

    def test_excludes_git_dir(self):
        assert should_exclude_path(Path(".git/config")) is True

    def test_excludes_hypothesis_dir(self):
        assert should_exclude_path(Path(".hypothesis/constants/abc")) is True

    def test_excludes_logs_dir(self):
        assert should_exclude_path(Path("logs/audit.log")) is True

    def test_excludes_data_dir(self):
        assert should_exclude_path(Path("data/contexts.json")) is True

    def test_includes_config_yaml(self):
        assert should_exclude_path(Path("config/config.yaml")) is False

    def test_includes_source_file(self):
        assert should_exclude_path(Path("src/main.py")) is False

    def test_includes_test_file(self):
        assert should_exclude_path(Path("tests/unit/test_clone.py")) is False


class TestFileContainsSecrets:
    """Tests for file-level secret detection."""

    def test_detects_secrets_in_file(self, tmp_path):
        secret_file = tmp_path / "secrets.env"
        secret_file.write_text(
            "GROQ_API_KEY=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
        )
        assert file_contains_secrets(secret_file) is True

    def test_clean_file_passes(self, tmp_path):
        clean_file = tmp_path / "config.yaml"
        clean_file.write_text("bot:\n  name: openclaw\n")
        assert file_contains_secrets(clean_file) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        missing = tmp_path / "nonexistent.txt"
        assert file_contains_secrets(missing) is False


class TestCollectFiles:
    """Tests for file collection logic."""

    def test_collects_config_files(self, tmp_path):
        # Create minimal project structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("bot: {}")
        (config_dir / "permissions.yaml").write_text("admins: []")
        (config_dir / ".env").write_text("SECRET=value")

        files = collect_files(tmp_path)
        arcnames = [arcname for _, arcname in files]

        assert "config/config.yaml" in arcnames
        assert "config/permissions.yaml" in arcnames
        # .env should NOT be collected (it's not in CONFIG_FILES list)

    def test_collects_source_files(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (src_dir / "main.py").write_text("print('hello')")

        files = collect_files(tmp_path)
        arcnames = [arcname for _, arcname in files]

        assert "src/__init__.py" in arcnames
        assert "src/main.py" in arcnames

    def test_excludes_pycache_from_source(self, tmp_path):
        src_dir = tmp_path / "src" / "__pycache__"
        src_dir.mkdir(parents=True)
        (src_dir / "main.cpython-313.pyc").write_bytes(b"\x00")

        files = collect_files(tmp_path)
        arcnames = [arcname for _, arcname in files]

        assert not any("__pycache__" in name for name in arcnames)

    def test_collects_project_files(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "install.py").write_text("print('install')")

        files = collect_files(tmp_path)
        arcnames = [arcname for _, arcname in files]

        assert "pyproject.toml" in arcnames
        assert "README.md" in arcnames
        assert "install.py" in arcnames


class TestValidateNoSecrets:
    """Tests for archive validation."""

    def test_clean_archive_passes(self, tmp_path):
        archive_path = tmp_path / "clean.tar.gz"
        with tarfile.open(str(archive_path), "w:gz") as tar:
            # Add a clean file
            import io

            content = b"bot:\n  name: openclaw\n"
            info = tarfile.TarInfo(name="openclaw/config.yaml")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        violations = validate_no_secrets(archive_path)
        assert violations == []

    def test_detects_env_file_in_archive(self, tmp_path):
        archive_path = tmp_path / "tainted.tar.gz"
        with tarfile.open(str(archive_path), "w:gz") as tar:
            import io

            content = b"GROQ_API_KEY=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
            info = tarfile.TarInfo(name="openclaw/config/.env")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        violations = validate_no_secrets(archive_path)
        assert len(violations) > 0
        assert any(".env" in v for v in violations)

    def test_detects_secret_content_in_archive(self, tmp_path):
        archive_path = tmp_path / "tainted2.tar.gz"
        with tarfile.open(str(archive_path), "w:gz") as tar:
            import io

            content = b"key=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
            info = tarfile.TarInfo(name="openclaw/leaked.txt")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        violations = validate_no_secrets(archive_path)
        assert len(violations) > 0


class TestCloneExporter:
    """Integration tests for the full export flow."""

    def test_export_creates_archive(self, tmp_path):
        # Create minimal project structure
        project = tmp_path / "project"
        project.mkdir()
        config_dir = project / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("bot:\n  name: test\n")
        (config_dir / "permissions.yaml").write_text("admins: []\n")
        (config_dir / ".env").write_text(
            "GROQ_API_KEY=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
        )
        src_dir = project / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (project / "pyproject.toml").write_text("[project]\nname='test'")

        output = tmp_path / "output.tar.gz"
        exporter = CloneExporter(str(project))
        result = exporter.export(str(output))

        assert result == output
        assert output.exists()

    def test_export_excludes_env_file(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        config_dir = project / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("bot: {}")
        (config_dir / ".env").write_text(
            "GROQ_API_KEY=gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"
        )

        output = tmp_path / "output.tar.gz"
        exporter = CloneExporter(str(project))
        exporter.export(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert not any(name.endswith(".env") for name in names)

    def test_export_includes_env_template(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        config_dir = project / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("bot: {}")

        output = tmp_path / "output.tar.gz"
        exporter = CloneExporter(str(project))
        exporter.export(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any(".env.template" in name for name in names)

            # Verify template content has placeholder values
            for member in tar.getmembers():
                if ".env.template" in member.name:
                    f = tar.extractfile(member)
                    content = f.read().decode("utf-8")
                    assert "your_telegram_bot_token_here" in content
                    assert "your_groq_api_key_here" in content
                    break

    def test_export_excludes_source_files_with_secrets(self, tmp_path):
        """Source files containing real API keys are excluded during collection."""
        project = tmp_path / "project"
        project.mkdir()
        src_dir = project / "src"
        src_dir.mkdir()
        # A source file that accidentally contains a real API key
        (src_dir / "leaked.py").write_text(
            'API_KEY = "gsk_aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7"'
        )
        # A clean source file
        (src_dir / "clean.py").write_text("print('hello')")

        output = tmp_path / "output.tar.gz"
        exporter = CloneExporter(str(project))
        exporter.export(str(output))

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            # leaked.py should NOT be in the archive
            assert not any("leaked.py" in name for name in names)
            # clean.py should be in the archive
            assert any("clean.py" in name for name in names)
