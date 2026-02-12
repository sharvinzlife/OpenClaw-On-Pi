"""Unit tests for SystemInfoSkill."""

import pytest

from src.skills.sysinfo import (
    SystemInfoSkill,
    _read_cpu_percent,
    _read_disk,
    _read_memory,
    _read_temperature,
    _read_uptime,
)


@pytest.fixture
def skill():
    return SystemInfoSkill(config={"enabled": True})


class TestHelperFunctions:
    """Tests for the individual reader functions."""

    def test_read_cpu_percent_returns_string(self):
        result = _read_cpu_percent()
        assert isinstance(result, str)
        # Either a number or "N/A"
        if result != "N/A":
            float(result)  # Should not raise

    def test_read_temperature_returns_string(self):
        result = _read_temperature()
        assert isinstance(result, str)
        if result != "N/A":
            float(result)

    def test_read_memory_returns_tuple(self):
        used, total, pct = _read_memory()
        assert isinstance(used, str)
        assert isinstance(total, str)
        assert isinstance(pct, str)

    def test_read_uptime_returns_string(self):
        result = _read_uptime()
        assert isinstance(result, str)
        # Either formatted or "N/A"
        if result != "N/A":
            assert "d" in result and "h" in result and "m" in result

    def test_read_disk_returns_tuple(self):
        used, total, pct = _read_disk()
        assert isinstance(used, str)
        assert isinstance(total, str)
        assert isinstance(pct, str)
        # Disk should always work (shutil.disk_usage)
        if used != "N/A":
            float(used)
            float(total)
            float(pct)


class TestSystemInfoSkillExecute:
    """Tests for SystemInfoSkill.execute()."""

    @pytest.mark.asyncio
    async def test_returns_formatted_output(self, skill):
        result = await skill.execute(user_id=1, args=[])
        assert result.error is None
        assert result.text is not None
        # Check all expected emoji prefixes
        assert "🖥️ CPU:" in result.text
        assert "🌡️ Temp:" in result.text
        assert "💾 RAM:" in result.text
        assert "💿 Disk:" in result.text
        assert "⏱️ Uptime:" in result.text

    @pytest.mark.asyncio
    async def test_output_has_five_lines(self, skill):
        result = await skill.execute(user_id=1, args=[])
        lines = result.text.strip().split("\n")
        assert len(lines) == 5

    @pytest.mark.asyncio
    async def test_class_attributes(self):
        assert SystemInfoSkill.name == "sysinfo"
        assert SystemInfoSkill.command == "sysinfo"
        assert SystemInfoSkill.permission_level == "admin"

    @pytest.mark.asyncio
    async def test_check_dependencies(self):
        assert SystemInfoSkill.check_dependencies() is True
