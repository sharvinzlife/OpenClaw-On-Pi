"""System info skill — display system stats from /proc and shutil."""

import shutil
from pathlib import Path

from src.skills.base_skill import BaseSkill, SkillResult


def _read_cpu_percent() -> str:
    """Read CPU usage percentage from /proc/stat.

    Compares two snapshots of /proc/stat to calculate usage.
    Falls back to 'N/A' if /proc/stat is unavailable.
    """
    import time

    stat_path = Path("/proc/stat")
    if not stat_path.exists():
        return "N/A"

    def read_cpu_times() -> list[int]:
        line = stat_path.read_text().splitlines()[0]  # "cpu  ..."
        return [int(x) for x in line.split()[1:]]

    try:
        t1 = read_cpu_times()
        time.sleep(0.1)
        t2 = read_cpu_times()

        delta = [b - a for a, b in zip(t1, t2)]
        total = sum(delta)
        if total == 0:
            return "0.0"
        idle = delta[3]  # 4th field is idle
        usage = (1 - idle / total) * 100
        return f"{usage:.1f}"
    except Exception:
        return "N/A"


def _read_temperature() -> str:
    """Read CPU temperature from thermal zone.

    Returns:
        Temperature string like '45.0' or 'N/A' if unavailable.
    """
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if not temp_path.exists():
        return "N/A"
    try:
        millideg = int(temp_path.read_text().strip())
        return f"{millideg / 1000:.1f}"
    except Exception:
        return "N/A"


def _read_memory() -> tuple[str, str, str]:
    """Read memory info from /proc/meminfo.

    Returns:
        Tuple of (used_mb, total_mb, percent) as strings, or ('N/A', 'N/A', 'N/A').
    """
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        return ("N/A", "N/A", "N/A")

    try:
        info = {}
        for line in meminfo_path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                info[key] = int(parts[1])  # value in kB

        total_kb = info.get("MemTotal", 0)
        available_kb = info.get("MemAvailable", 0)
        used_kb = total_kb - available_kb

        total_mb = total_kb / 1024
        used_mb = used_kb / 1024
        percent = (used_kb / total_kb * 100) if total_kb > 0 else 0

        return (f"{used_mb:.0f}", f"{total_mb:.0f}", f"{percent:.1f}")
    except Exception:
        return ("N/A", "N/A", "N/A")


def _read_uptime() -> str:
    """Read system uptime from /proc/uptime.

    Returns:
        Formatted string like '2d 5h 30m' or 'N/A'.
    """
    uptime_path = Path("/proc/uptime")
    if not uptime_path.exists():
        return "N/A"

    try:
        seconds = float(uptime_path.read_text().split()[0])
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{days}d {hours}h {minutes}m"
    except Exception:
        return "N/A"


def _read_disk() -> tuple[str, str, str]:
    """Read disk usage via shutil.disk_usage('/').

    Returns:
        Tuple of (used_gb, total_gb, percent) as strings.
    """
    try:
        usage = shutil.disk_usage("/")
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        percent = (usage.used / usage.total * 100) if usage.total > 0 else 0
        return (f"{used_gb:.1f}", f"{total_gb:.1f}", f"{percent:.1f}")
    except Exception:
        return ("N/A", "N/A", "N/A")


class SystemInfoSkill(BaseSkill):
    """Show system stats — CPU, temp, RAM, disk, uptime (admin only)."""

    name = "sysinfo"
    command = "sysinfo"
    description = "Show system stats (admin only)"
    permission_level = "admin"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        """Gather and format system information.

        Args:
            user_id: Telegram user ID.
            args: Not used.

        Returns:
            SkillResult with formatted system stats.
        """
        cpu = _read_cpu_percent()
        temp = _read_temperature()
        ram_used, ram_total, ram_pct = _read_memory()
        disk_used, disk_total, disk_pct = _read_disk()
        uptime = _read_uptime()

        lines = [
            f"🖥️ CPU: {cpu}%",
            f"🌡️ Temp: {temp}°C",
            f"💾 RAM: {ram_used}/{ram_total} MB ({ram_pct}%)",
            f"💿 Disk: {disk_used}/{disk_total} GB ({disk_pct}%)",
            f"⏱️ Uptime: {uptime}",
        ]

        return SkillResult(text="\n".join(lines))

    @classmethod
    def check_dependencies(cls) -> bool:
        """No external dependencies needed."""
        return True
