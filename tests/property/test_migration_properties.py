"""Property-based tests for migration script.

Feature: openclaw-telegram-bot
Tests Property 21 from the design document.
"""

import io
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck, assume

from scripts.migrate import (
    MigrationManager,
    compute_sha256,
    compute_file_sha256,
)


# --- Strategies ---

# Characters safe for content (printable ASCII, no NUL bytes)
safe_chars = st.characters(whitelist_categories=("L", "N", "P", "S", "Z"))

# User IDs (realistic Telegram user IDs)
user_id_strategy = st.integers(min_value=1, max_value=10**12).map(str)

# Message roles
message_role_strategy = st.sampled_from(["user", "assistant"])


@st.composite
def message_strategy(draw):
    """Generate a single conversation message with role and content."""
    role = draw(message_role_strategy)
    content = draw(
        st.text(
            min_size=1,
            max_size=200,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Z")
            ),
        ).filter(lambda x: x.strip())
    )
    return {"role": role, "content": content}


@st.composite
def conversation_context_strategy(draw):
    """Generate a dict of user_id -> conversation context (as stored in contexts.json)."""
    num_users = draw(st.integers(min_value=1, max_value=3))
    contexts = {}
    for _ in range(num_users):
        uid = draw(user_id_strategy)
        assume(uid not in contexts)  # unique user IDs
        messages = draw(st.lists(message_strategy(), min_size=1, max_size=5))
        contexts[uid] = {
            "user_id": int(uid),
            "messages": messages,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:31:00Z",
            "total_tokens": draw(st.integers(min_value=0, max_value=50000)),
        }
    return contexts


@st.composite
def usage_stats_strategy(draw):
    """Generate usage statistics dict (as stored in usage_stats.json)."""
    providers = draw(
        st.lists(
            st.sampled_from(["groq", "ollama_cloud", "ollama_local"]),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    stats = {}
    for provider in providers:
        stats[provider] = {
            "total_requests": draw(st.integers(min_value=0, max_value=100000)),
            "total_tokens": draw(st.integers(min_value=0, max_value=1000000)),
        }
    return stats


@st.composite
def config_yaml_strategy(draw):
    """Generate valid config.yaml content."""
    provider = draw(st.sampled_from(["groq", "ollama_cloud", "ollama_local"]))
    timeout = draw(st.integers(min_value=5, max_value=120))
    return (
        f"bot:\n"
        f"  default_provider: {provider}\n"
        f"  response_timeout: {timeout}\n"
    )


def _create_project_with_data(
    tmp_path: Path,
    contexts: Dict[str, Any],
    usage_stats: Dict[str, Any],
    config_content: str,
) -> Path:
    """Create a project directory with the given data files.

    Returns the project directory path.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Config files
    config_dir = project_dir / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(config_content)
    (config_dir / "permissions.yaml").write_text("admins: []\nusers: []\n")
    (config_dir / "providers.yaml").write_text("groq:\n  enabled: true\n")

    # Data files
    data_dir = project_dir / "data"
    data_dir.mkdir()
    (data_dir / "contexts.json").write_text(json.dumps(contexts, indent=2))
    (data_dir / "usage_stats.json").write_text(json.dumps(usage_stats, indent=2))

    # pyproject.toml (for version detection)
    (project_dir / "pyproject.toml").write_text(
        '[project]\nname = "openclaw"\nversion = "0.2.0"\n'
    )

    return project_dir


class TestBackupRestoreRoundTrip:
    """Property 21: Backup/Restore Round-Trip

    For any complete backup created with --backup, restoring with --restore
    SHALL result in equivalent conversation contexts and usage statistics
    as the original system.

    **Validates: Requirements 13.3**
    """

    @given(
        contexts=conversation_context_strategy(),
        usage_stats=usage_stats_strategy(),
        config_content=config_yaml_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_backup_restore_preserves_contexts(
        self,
        contexts: Dict[str, Any],
        usage_stats: Dict[str, Any],
        config_content: str,
    ):
        """Property 21: Backup then restore preserves conversation contexts byte-for-byte.

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create source project with data
            source_dir = _create_project_with_data(
                tmp_path, contexts, usage_stats, config_content
            )
            original_contexts_bytes = (source_dir / "data" / "contexts.json").read_bytes()

            # Backup
            manager = MigrationManager(project_dir=str(source_dir))
            archive_path = manager.backup(
                output_path=str(tmp_path / "backup.tar.gz")
            )

            # Restore to a fresh directory
            restore_dir = tmp_path / "restored"
            restore_dir.mkdir()
            # Create minimal structure for restore target
            (restore_dir / "config").mkdir()
            (restore_dir / "data").mkdir()

            restore_manager = MigrationManager(project_dir=str(restore_dir))
            result = restore_manager.restore(archive_path=str(archive_path))

            assert not result["errors"], f"Restore had errors: {result['errors']}"

            # Verify contexts.json is byte-for-byte equivalent
            restored_contexts_bytes = (restore_dir / "data" / "contexts.json").read_bytes()
            assert restored_contexts_bytes == original_contexts_bytes, (
                "Restored contexts.json must be byte-for-byte equivalent to original"
            )

    @given(
        contexts=conversation_context_strategy(),
        usage_stats=usage_stats_strategy(),
        config_content=config_yaml_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_backup_restore_preserves_usage_stats(
        self,
        contexts: Dict[str, Any],
        usage_stats: Dict[str, Any],
        config_content: str,
    ):
        """Property 21: Backup then restore preserves usage statistics byte-for-byte.

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            source_dir = _create_project_with_data(
                tmp_path, contexts, usage_stats, config_content
            )
            original_stats_bytes = (source_dir / "data" / "usage_stats.json").read_bytes()

            # Backup
            manager = MigrationManager(project_dir=str(source_dir))
            archive_path = manager.backup(
                output_path=str(tmp_path / "backup.tar.gz")
            )

            # Restore to fresh directory
            restore_dir = tmp_path / "restored"
            restore_dir.mkdir()
            (restore_dir / "config").mkdir()
            (restore_dir / "data").mkdir()

            restore_manager = MigrationManager(project_dir=str(restore_dir))
            result = restore_manager.restore(archive_path=str(archive_path))

            assert not result["errors"], f"Restore had errors: {result['errors']}"

            restored_stats_bytes = (restore_dir / "data" / "usage_stats.json").read_bytes()
            assert restored_stats_bytes == original_stats_bytes, (
                "Restored usage_stats.json must be byte-for-byte equivalent to original"
            )

    @given(
        contexts=conversation_context_strategy(),
        usage_stats=usage_stats_strategy(),
        config_content=config_yaml_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_backup_restore_preserves_config(
        self,
        contexts: Dict[str, Any],
        usage_stats: Dict[str, Any],
        config_content: str,
    ):
        """Property 21: Backup then restore preserves config files byte-for-byte.

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            source_dir = _create_project_with_data(
                tmp_path, contexts, usage_stats, config_content
            )
            original_config_bytes = (source_dir / "config" / "config.yaml").read_bytes()

            # Backup
            manager = MigrationManager(project_dir=str(source_dir))
            archive_path = manager.backup(
                output_path=str(tmp_path / "backup.tar.gz")
            )

            # Restore to fresh directory
            restore_dir = tmp_path / "restored"
            restore_dir.mkdir()
            (restore_dir / "config").mkdir()
            (restore_dir / "data").mkdir()

            restore_manager = MigrationManager(project_dir=str(restore_dir))
            result = restore_manager.restore(archive_path=str(archive_path))

            assert not result["errors"], f"Restore had errors: {result['errors']}"

            restored_config_bytes = (restore_dir / "config" / "config.yaml").read_bytes()
            assert restored_config_bytes == original_config_bytes, (
                "Restored config.yaml must be byte-for-byte equivalent to original"
            )


class TestSha256Determinism:
    """SHA-256 checksums are deterministic: same input always produces same output.

    **Validates: Requirements 13.3**
    """

    @given(data=st.binary(min_size=0, max_size=10000))
    @settings(max_examples=100, deadline=None)
    def test_sha256_deterministic(self, data: bytes):
        """Property 21: compute_sha256 is deterministic — same input always yields same hash.

        **Validates: Requirements 13.3**
        """
        hash1 = compute_sha256(data)
        hash2 = compute_sha256(data)
        assert hash1 == hash2, "SHA-256 must be deterministic"

    @given(
        data1=st.binary(min_size=1, max_size=5000),
        data2=st.binary(min_size=1, max_size=5000),
    )
    @settings(max_examples=100, deadline=None)
    def test_sha256_different_inputs_different_hashes(
        self, data1: bytes, data2: bytes
    ):
        """Property 21: Different inputs produce different SHA-256 hashes (collision resistance).

        **Validates: Requirements 13.3**
        """
        assume(data1 != data2)
        assert compute_sha256(data1) != compute_sha256(data2), (
            "Different inputs should produce different hashes"
        )

    @given(data=st.binary(min_size=0, max_size=5000))
    @settings(max_examples=100, deadline=None)
    def test_file_sha256_matches_data_sha256(self, data: bytes):
        """Property 21: compute_file_sha256 produces the same hash as compute_sha256 for the same content.

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_file.bin"
            filepath.write_bytes(data)
            assert compute_file_sha256(filepath) == compute_sha256(data), (
                "File hash must match data hash for identical content"
            )


class TestIntegrityValidation:
    """Integrity validation properties for backup archives.

    **Validates: Requirements 13.3**
    """

    @given(
        contexts=conversation_context_strategy(),
        usage_stats=usage_stats_strategy(),
        config_content=config_yaml_strategy(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_backup_always_passes_integrity(
        self,
        contexts: Dict[str, Any],
        usage_stats: Dict[str, Any],
        config_content: str,
    ):
        """Property 21: A freshly created backup always passes integrity validation (no false positives).

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            source_dir = _create_project_with_data(
                tmp_path, contexts, usage_stats, config_content
            )

            manager = MigrationManager(project_dir=str(source_dir))
            archive_path = manager.backup(
                output_path=str(tmp_path / "backup.tar.gz")
            )

            violations = manager.validate_integrity(archive_path)
            assert violations == [], (
                f"Fresh backup must pass integrity validation, got: {violations}"
            )

    @given(
        contexts=conversation_context_strategy(),
        usage_stats=usage_stats_strategy(),
        config_content=config_yaml_strategy(),
        tamper_content=st.binary(min_size=1, max_size=500),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_tampered_archive_fails_integrity(
        self,
        contexts: Dict[str, Any],
        usage_stats: Dict[str, Any],
        config_content: str,
        tamper_content: bytes,
    ):
        """Property 21: Tampered archives always fail integrity validation.

        **Validates: Requirements 13.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            source_dir = _create_project_with_data(
                tmp_path, contexts, usage_stats, config_content
            )

            manager = MigrationManager(project_dir=str(source_dir))
            archive_path = manager.backup(
                output_path=str(tmp_path / "backup.tar.gz")
            )

            # Read the original archive, tamper with a file, and rewrite
            tampered_path = tmp_path / "tampered.tar.gz"
            manifest_data = None

            with tarfile.open(str(archive_path), "r:gz") as original:
                # Read manifest first
                for member in original.getmembers():
                    if member.name.endswith("manifest.json"):
                        f = original.extractfile(member)
                        if f:
                            manifest_data = json.loads(f.read().decode("utf-8"))
                        break

                # Rewrite archive with one file tampered
                with tarfile.open(str(tampered_path), "w:gz") as tampered:
                    tampered_any = False
                    for member in original.getmembers():
                        if not member.isfile():
                            continue
                        f = original.extractfile(member)
                        if f is None:
                            continue
                        data = f.read()

                        # Tamper with the first non-manifest file
                        if (
                            not tampered_any
                            and not member.name.endswith("manifest.json")
                        ):
                            # Only tamper if content actually changes
                            if data != tamper_content:
                                data = tamper_content
                                tampered_any = True

                        info = tarfile.TarInfo(name=member.name)
                        info.size = len(data)
                        info.mtime = member.mtime
                        tampered.addfile(info, io.BytesIO(data))

            # If we couldn't tamper (unlikely edge case), skip
            assume(tampered_any)

            violations = manager.validate_integrity(
                tampered_path, manifest=manifest_data
            )
            assert len(violations) > 0, (
                "Tampered archive must fail integrity validation"
            )
