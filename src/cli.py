#!/usr/bin/env python3
"""Epic Neon CLI for OpenClaw Telegram Bot - Made with ❤️ by Sharvinzlife 👑"""

import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 🎨 NEON ANSI Colors & Styles
# ═══════════════════════════════════════════════════════════════


class C:
    """Neon color codes."""

    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"
    # Neon palette
    RED = "\033[38;5;196m"
    GREEN = "\033[38;5;46m"
    YELLOW = "\033[38;5;226m"
    BLUE = "\033[38;5;33m"
    CYAN = "\033[38;5;51m"
    MAGENTA = "\033[38;5;201m"
    ORANGE = "\033[38;5;208m"
    CORAL = "\033[38;5;209m"
    SALMON = "\033[38;5;210m"
    PEACH = "\033[38;5;216m"
    GOLD = "\033[38;5;220m"
    AMBER = "\033[38;5;214m"
    PINK = "\033[38;5;213m"
    LAVENDER = "\033[38;5;183m"
    SKY = "\033[38;5;117m"
    MINT = "\033[38;5;121m"
    LIME = "\033[38;5;154m"
    PURPLE = "\033[38;5;135m"
    NEON_GREEN = "\033[38;5;118m"
    NEON_PINK = "\033[38;5;199m"
    NEON_BLUE = "\033[38;5;39m"
    NEON_CYAN = "\033[38;5;87m"
    NEON_ORANGE = "\033[38;5;202m"
    NEON_YELLOW = "\033[38;5;227m"
    WHITE = "\033[38;5;255m"
    GRAY = "\033[38;5;245m"
    DARK = "\033[38;5;238m"


NEON = [
    C.NEON_PINK,
    C.NEON_ORANGE,
    C.NEON_YELLOW,
    C.NEON_GREEN,
    C.NEON_CYAN,
    C.NEON_BLUE,
    C.MAGENTA,
]
WARM = [C.PEACH, C.SALMON, C.CORAL, C.ORANGE, C.AMBER, C.GOLD]
FIRE = [C.RED, C.NEON_ORANGE, C.ORANGE, C.AMBER, C.GOLD, C.NEON_YELLOW]


# ═══════════════════════════════════════════════════════════════
# ✨ Animation Engine
# ═══════════════════════════════════════════════════════════════


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def rainbow_text(text: str, colors=None) -> str:
    """Apply rainbow gradient to text."""
    palette = colors or NEON
    result = []
    ci = 0
    for ch in text:
        if ch.strip():
            result.append(f"{palette[ci % len(palette)]}{ch}")
            ci += 1
        else:
            result.append(ch)
    result.append(C.END)
    return "".join(result)


def neon_glow(text: str, color: str) -> str:
    """Make text look like it's glowing."""
    return f"{C.BOLD}{color}{text}{C.END}"


def typewriter(text: str, delay: float = 0.015):
    """Type text character by character."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def spinner(msg: str, duration: float = 1.0):
    """Neon spinner animation."""
    frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
    colors = [C.NEON_PINK, C.NEON_ORANGE, C.NEON_YELLOW, C.NEON_GREEN, C.NEON_CYAN, C.NEON_BLUE]
    end = time.time() + duration
    i = 0
    while time.time() < end:
        c = colors[i % len(colors)]
        f = frames[i % len(frames)]
        sys.stdout.write(f"\r  {c}{C.BOLD}{f}{C.END} {msg}")
        sys.stdout.flush()
        time.sleep(0.07)
        i += 1
    sys.stdout.write(f"\r  {C.NEON_GREEN}{C.BOLD}✓{C.END} {msg}\n")
    sys.stdout.flush()


def progress_bar(msg: str, duration: float = 1.0, width: int = 30):
    """Animated neon progress bar."""
    steps = width
    for i in range(steps + 1):
        pct = i / steps
        filled = int(width * pct)
        # Gradient fill
        bar = ""
        for j in range(filled):
            bar += f"{NEON[j % len(NEON)]}█"
        bar += f"{C.DARK}{'░' * (width - filled)}"
        sys.stdout.write(
            f"\r  {C.GRAY}[{bar}{C.GRAY}]{C.END} {C.WHITE}{int(pct*100):3d}%{C.END} {msg}"
        )
        sys.stdout.flush()
        time.sleep(duration / steps)
    sys.stdout.write(f'\r  {C.NEON_GREEN}{C.BOLD}[{"█" * width}] 100%{C.END} {msg}\n')
    sys.stdout.flush()


def matrix_rain(lines: int = 3, width: int = 60, duration: float = 0.8):
    """Quick matrix-style rain effect."""
    chars = "01アイウエオカキクケコサシスセソ🦞"
    end = time.time() + duration
    while time.time() < end:
        line = ""
        for _ in range(width):
            if random.random() < 0.3:
                c = random.choice([C.NEON_GREEN, C.MINT, C.LIME, C.GREEN])
                line += f"{c}{random.choice(chars)}"
            else:
                line += " "
        print(f"  {line}{C.END}")
        time.sleep(0.06)


def pulse_text(text: str, cycles: int = 2):
    """Pulse text between bright and dim."""
    for _ in range(cycles):
        sys.stdout.write(f"\r  {C.BOLD}{C.NEON_ORANGE}{text}{C.END}")
        sys.stdout.flush()
        time.sleep(0.15)
        sys.stdout.write(f"\r  {C.DIM}{C.ORANGE}{text}{C.END}")
        sys.stdout.flush()
        time.sleep(0.15)
    sys.stdout.write(f"\r  {C.BOLD}{C.NEON_ORANGE}{text}{C.END}\n")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════
# 🦞 Banner & Branding
# ═══════════════════════════════════════════════════════════════

LOBSTER_ART = r"""
       ___
      /   \    🦞
     | o o |  /
      \ _ /--'
     /|   |\
    / |   | \
   ~  ~   ~  ~
"""


def print_banner():
    """Epic animated neon banner."""
    clear()

    # Matrix intro
    matrix_rain(3, 60, 0.4)

    # Banner with fire gradient
    banner = [
        "   ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗",
        "  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██║     ██╔══██╗██║    ██║",
        "  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║     ███████║██║ █╗ ██║",
        "  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║     ██╔══██║██║███╗██║",
        "  ╚██████╔╝██║     ███████╗██║ ╚████║╚██████╗███████╗██║  ██║╚███╔███╔╝",
        "   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝",
    ]

    print()
    for i, line in enumerate(banner):
        color = FIRE[i % len(FIRE)]
        print(f"  {C.BOLD}{color}{line}{C.END}")
        time.sleep(0.04)

    print()

    # Animated tagline
    tagline = "⚡ AI-Powered Telegram Bot on Raspberry Pi ⚡"
    print(f"  {rainbow_text(tagline)}")

    # Provider badges
    print(
        f"\n  {neon_glow('🧠 Groq', C.NEON_CYAN)}  {C.DARK}│{C.END}  {neon_glow('☁️  Ollama Cloud', C.NEON_GREEN)}  {C.DARK}│{C.END}  {neon_glow('🖥️  Local Ollama', C.NEON_ORANGE)}"
    )

    # Neon separator
    sep = "━" * 62
    print(f"\n  {rainbow_text(sep)}")

    # Branding footer
    print_credit_line()


def print_credit_line():
    """Print the credit/social line."""
    print(
        f"\n  {C.DIM}Made with {C.END}{C.RED}❤️{C.END}{C.DIM} by {C.END}{C.BOLD}{C.NEON_ORANGE}Sharvinzlife{C.END} {C.GOLD}👑{C.END}"
    )
    print(f"  {C.DARK}├─{C.END} {C.NEON_BLUE}🌐 github.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}├─{C.END} {C.NEON_PINK}📸 instagram.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}├─{C.END} {C.NEON_CYAN}🐦 x.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}└─{C.END} {C.BLUE}📘 fb.com/sharvinzlife{C.END}")


def print_header(text: str):
    """Neon section header."""
    sep = "═" * 58
    print(f"\n  {C.NEON_ORANGE}{C.BOLD}{sep}{C.END}")
    typewriter(f"  {C.BOLD}{C.NEON_ORANGE}  {text}{C.END}", 0.01)
    print(f"  {C.NEON_ORANGE}{C.BOLD}{sep}{C.END}\n")


def print_mini_banner():
    """Smaller banner for sub-screens."""
    print(
        f"\n  {C.BOLD}{C.NEON_ORANGE}🦞 OpenClaw{C.END} {C.DARK}│{C.END} {C.DIM}AI Telegram Bot{C.END} {C.DARK}│{C.END} {C.DIM}Made with {C.RED}❤️{C.END}{C.DIM} by {C.NEON_ORANGE}Sharvinzlife {C.GOLD}👑{C.END}"
    )
    print(f"  {C.DARK}{'─' * 62}{C.END}")


# ═══════════════════════════════════════════════════════════════
# 🎮 UI Components
# ═══════════════════════════════════════════════════════════════


def menu_item(key: str, text: str, emoji: str = "", color=None):
    """Neon menu item."""
    c = color or C.NEON_CYAN
    e = f"{emoji} " if emoji else ""
    print(f"    {C.BOLD}{c}[{key}]{C.END}  {e}{C.WHITE}{text}{C.END}")


def success(text: str):
    print(f"  {C.NEON_GREEN}{C.BOLD}✓{C.END} {text}")


def error(text: str):
    print(f"  {C.RED}{C.BOLD}✗{C.END} {text}")


def warn(text: str):
    print(f"  {C.NEON_YELLOW}{C.BOLD}⚠{C.END} {text}")


def info(text: str):
    print(f"  {C.NEON_CYAN}ℹ{C.END} {C.DIM}{text}{C.END}")


def get_input(prompt: str, default: str = "") -> str:
    dflt = f" {C.DARK}({default}){C.END}" if default else ""
    try:
        val = input(f"\n  {C.NEON_ORANGE}{C.BOLD}❯{C.END} {prompt}{dflt}: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def confirm(prompt: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    try:
        val = input(f"\n  {C.NEON_ORANGE}{C.BOLD}❯{C.END} {prompt} [{d}]: ").strip().lower()
        if not val:
            return default
        return val in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def get_project_dir() -> Path:
    return Path(__file__).parent.parent.resolve()


def check_config_exists() -> tuple[bool, Path]:
    project_dir = get_project_dir()
    env_file = project_dir / "config" / ".env"
    return env_file.exists(), env_file


# ═══════════════════════════════════════════════════════════════
# 📋 Main Menu
# ═══════════════════════════════════════════════════════════════


def show_main_menu():
    """Epic neon main menu."""
    print_banner()

    print(f"\n  {C.BOLD}{C.WHITE}🦞 What would you like to do?{C.END}\n")

    items = [
        ("1", "Start the bot", "🚀", C.NEON_GREEN),
        ("2", "Configure API keys", "🔑", C.NEON_YELLOW),
        ("3", "Edit permissions", "🔒", C.NEON_ORANGE),
        ("4", "Check status", "⚙️", C.NEON_CYAN),
        ("5", "Run tests", "🧪", C.NEON_BLUE),
        ("6", "Start dashboard only", "🌐", C.NEON_PINK),
        ("q", "Quit", "👋", C.DARK),
    ]

    for key, text, emoji, color in items:
        menu_item(key, text, emoji, color)
        time.sleep(0.04)

    print()
    return get_input("Select option", "1")


# ═══════════════════════════════════════════════════════════════
# 🔑 Configuration
# ═══════════════════════════════════════════════════════════════


def configure_env_interactive():
    """Interactive neon configuration."""
    clear()
    print_mini_banner()
    print_header("🔑 API Key Configuration")

    project_dir = get_project_dir()
    config_dir = project_dir / "config"
    env_file = config_dir / ".env"

    print(f"  {C.DARK}📁{C.END} Config: {C.NEON_CYAN}{config_dir}{C.END}")
    print(f"  {C.DARK}📄{C.END} Env:    {C.NEON_CYAN}{env_file}{C.END}")

    if not env_file.exists():
        template = config_dir / ".env.template"
        if template.exists():
            shutil.copy(template, env_file)
            success("Created .env from template")
        else:
            env_file.touch()
            success("Created new .env file")

    print(f"\n  {C.BOLD}Choose method:{C.END}\n")
    menu_item("1", "Paste values directly (recommended)", "⚡", C.NEON_GREEN)
    menu_item("2", "Open in nano editor", "✏️", C.NEON_CYAN)
    menu_item("3", "Open in vim editor", "✏️", C.NEON_BLUE)
    menu_item("4", "Show current values", "👁️", C.NEON_YELLOW)
    menu_item("b", "Back", "↩️", C.DARK)

    choice = get_input("Select option", "1")

    if choice == "1":
        configure_paste_mode(env_file)
    elif choice == "2":
        open_editor(env_file, "nano")
    elif choice == "3":
        open_editor(env_file, "vim")
    elif choice == "4":
        show_current_config(env_file)
    elif choice.lower() == "b":
        return

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


def _load_env(env_file: Path) -> dict:
    """Load existing .env values into a dict."""
    existing = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                existing[key.strip()] = value.strip()
    return existing


def _save_env(env_file: Path, existing: dict):
    """Write env dict back to .env file."""
    out = [
        "# OpenClaw Telegram Bot - Environment Configuration",
        "",
        "# Required: Telegram Bot Token from @BotFather",
        f"TELEGRAM_BOT_TOKEN={existing.get('TELEGRAM_BOT_TOKEN', '')}",
        "",
        "# LLM Provider (need at least ONE — Groq or Ollama Cloud)",
        "",
        "# Groq API Key (free at console.groq.com)",
        "# Required for: /tts and /transcribe skills",
        f"GROQ_API_KEY={existing.get('GROQ_API_KEY', '')}",
        "",
        "# Ollama Cloud (free at ollama.com)",
        f"OLLAMA_CLOUD_URL={existing.get('OLLAMA_CLOUD_URL', '')}",
        f"OLLAMA_API_KEY={existing.get('OLLAMA_API_KEY', '')}",
        "",
        "# Reddit API (optional)",
        f"REDDIT_CLIENT_ID={existing.get('REDDIT_CLIENT_ID', '')}",
        f"REDDIT_CLIENT_SECRET={existing.get('REDDIT_CLIENT_SECRET', '')}",
    ]
    env_file.write_text("\n".join(out) + "\n")


def _mask(val: str) -> str:
    """Mask a secret value for display."""
    if not val:
        return "(not set)"
    if len(val) < 16:
        return val[:4] + "..." + val[-3:]
    return val[:8] + "..." + val[-4:]


KEYS_CONFIG = [
    {
        "key": "TELEGRAM_BOT_TOKEN",
        "label": "Telegram Bot Token",
        "icon": "\U0001f99e",
        "color_attr": "NEON_ORANGE",
        "hint": "Get from @BotFather on Telegram",
        "link": "https://t.me/BotFather",
        "prompt": "Token",
    },
    {
        "key": "GROQ_API_KEY",
        "label": "Groq API Key",
        "icon": "\U0001f9e0",
        "color_attr": "NEON_CYAN",
        "hint": "Free — needed for /tts & /transcribe skills",
        "link": "https://console.groq.com/keys",
        "prompt": "API Key",
    },
    {
        "key": "OLLAMA_API_KEY",
        "label": "Ollama Cloud API Key",
        "icon": "\U0001f511",
        "color_attr": "NEON_GREEN",
        "hint": "Free — alternative LLM provider",
        "link": "https://ollama.com/settings/keys",
        "prompt": "API Key",
    },
    {
        "key": "OLLAMA_CLOUD_URL",
        "label": "Ollama Cloud URL",
        "icon": "\u2601\ufe0f",
        "color_attr": "NEON_GREEN",
        "hint": "Default: https://ollama.com",
        "link": "",
        "prompt": "URL",
    },
    {
        "key": "REDDIT_CLIENT_ID",
        "label": "Reddit Client ID",
        "icon": "🔴",
        "color_attr": "NEON_ORANGE",
        "hint": "Create a script app on Reddit",
        "link": "https://www.reddit.com/prefs/apps",
        "prompt": "Client ID",
    },
    {
        "key": "REDDIT_CLIENT_SECRET",
        "label": "Reddit Client Secret",
        "icon": "🔴",
        "color_attr": "NEON_ORANGE",
        "hint": "The secret from your Reddit app",
        "link": "https://www.reddit.com/prefs/apps",
        "prompt": "Client Secret",
    },
]


def _configure_single_key(existing: dict, cfg: dict):
    """Prompt user for a single key value."""
    color = getattr(C, cfg["color_attr"], C.END)
    print(f"\n  {color}{cfg['icon']}  {cfg['label']}{C.END}")
    if cfg.get("link"):
        print(f"  {C.DIM}   {cfg['hint']}{C.END}")
        print(f"  {C.NEON_BLUE}   \u2192 {cfg['link']}{C.END}")
    else:
        print(f"  {C.DIM}   {cfg['hint']}{C.END}")
    cur = existing.get(cfg["key"], "")
    if cur:
        print(f"  {C.DIM}   Current: {_mask(cur)}{C.END}")
    val = get_input(cfg["prompt"])
    if val:
        existing[cfg["key"]] = val


def configure_paste_mode(env_file: Path):
    """Menu-based config — pick which key to configure."""
    existing = _load_env(env_file)

    while True:
        clear()
        print_mini_banner()
        print_header("\U0001f511 API Key Configuration")
        print(f"\n  {C.BOLD}Select a key to configure:{C.END}\n")

        for i, cfg in enumerate(KEYS_CONFIG, 1):
            color = getattr(C, cfg["color_attr"], C.END)
            val = existing.get(cfg["key"], "")
            if val:
                status = f"{C.GREEN}\u2713 Set{C.END}  {C.DIM}{_mask(val)}{C.END}"
            else:
                status = f"{C.RED}\u2717 Not set{C.END}"
            menu_item(str(i), f"{cfg['label']}  {status}", cfg["icon"], color)

        print()
        menu_item("a", "Configure all keys sequentially", "\u26a1", C.NEON_ORANGE)
        menu_item("s", "Save & back", "\U0001f4be", C.NEON_GREEN)
        print()

        choice = get_input("Select option", "s")

        if choice.lower() == "s":
            break
        elif choice.lower() == "a":
            for cfg in KEYS_CONFIG:
                _configure_single_key(existing, cfg)
            spinner("Saving configuration", 0.5)
            _save_env(env_file, existing)
            success("All keys saved!")
            input(f"\n  {C.DARK}Press Enter to continue...{C.END}")
        elif choice.isdigit() and 1 <= int(choice) <= len(KEYS_CONFIG):
            cfg = KEYS_CONFIG[int(choice) - 1]
            _configure_single_key(existing, cfg)
            spinner("Saving configuration", 0.5)
            _save_env(env_file, existing)
            success(f"{cfg['label']} saved!")
            input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


def setup_admin_user(permissions_file: Path):
    """Set up admin user."""
    user_id = get_input("Your Telegram User ID")
    if not user_id:
        info("Skipped admin setup")
        return
    if not user_id.isdigit():
        error("Invalid user ID - must be a number")
        return

    if permissions_file.exists():
        content = permissions_file.read_text()
    else:
        content = "admins:\n\nusers:\n\nguests:\n\nsettings:\n  allow_unknown_users: false\n"

    if f"- {user_id}" in content:
        info(f"User {user_id} already configured")
        return

    lines = content.splitlines()
    new_lines = []
    added = False
    for line in lines:
        new_lines.append(line)
        if line.strip() == "admins:" and not added:
            new_lines.append(f"  - {user_id}  # Added via CLI setup")
            added = True

    permissions_file.write_text("\n".join(new_lines) + "\n")
    success(f"Added user {user_id} as admin ⭐")


def open_editor(file_path: Path, editor: str):
    """Open file in editor."""
    print(f"\n  ✏️  Opening {file_path.name} in {editor}...")
    if not shutil.which(editor):
        error(f"{editor} not found")
        return
    subprocess.run([editor, str(file_path)])
    success(f"Closed {editor}")


def show_current_config(env_file: Path):
    """Show masked config values."""
    print(f"\n  {C.BOLD}📄 Current Configuration{C.END}\n")
    if not env_file.exists():
        warn("No .env file found")
        return
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if value and len(value) > 10:
                masked = f"{value[:5]}{'*' * 10}{value[-3:]}"
            elif value:
                masked = "*" * len(value)
            else:
                masked = f"{C.DIM}(not set){C.END}"
            icon = f"{C.NEON_GREEN}✓{C.END}" if value else f"{C.RED}✗{C.END}"
            print(f"    {icon} {C.NEON_CYAN}{key}{C.END}: {masked}")


# ═══════════════════════════════════════════════════════════════
# 🔒 Permissions, Status, Tests
# ═══════════════════════════════════════════════════════════════


def configure_permissions():
    """Configure user permissions."""
    clear()
    print_mini_banner()
    print_header("🔒 User Permissions")

    project_dir = get_project_dir()
    permissions_file = project_dir / "config" / "permissions.yaml"

    print(f"  {C.DARK}📄{C.END} File: {C.NEON_CYAN}{permissions_file}{C.END}")
    print(f"\n  {C.DIM}Get your Telegram User ID from @userinfobot{C.END}\n")

    menu_item("1", "Add admin user ID", "⭐", C.NEON_YELLOW)
    menu_item("2", "Open in nano", "✏️", C.NEON_CYAN)
    menu_item("3", "Open in vim", "✏️", C.NEON_BLUE)
    menu_item("b", "Back", "↩️", C.DARK)

    choice = get_input("Select option", "1")

    if choice == "1":
        user_id = get_input("Enter your Telegram User ID")
        if user_id and user_id.isdigit():
            content = permissions_file.read_text() if permissions_file.exists() else ""
            if f"- {user_id}" not in content:
                lines = content.splitlines()
                new_lines = []
                in_admins = False
                added = False
                for line in lines:
                    new_lines.append(line)
                    if line.strip() == "admins:":
                        in_admins = True
                    elif in_admins and not added:
                        new_lines.append(f"  - {user_id}  # Added via CLI")
                        added = True
                        in_admins = False
                permissions_file.write_text("\n".join(new_lines) + "\n")
                success(f"Added user {user_id} as admin")
            else:
                info(f"User {user_id} already in config")
    elif choice == "2":
        open_editor(permissions_file, "nano")
    elif choice == "3":
        open_editor(permissions_file, "vim")

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


def check_status():
    """Check bot status with neon indicators."""
    clear()
    print_mini_banner()
    print_header("⚙️  System Status")

    project_dir = get_project_dir()
    config_dir = project_dir / "config"

    # File checks with animation
    checks = [
        ("Config directory", config_dir.exists()),
        (".env file", (config_dir / ".env").exists()),
        ("permissions.yaml", (config_dir / "permissions.yaml").exists()),
        ("providers.yaml", (config_dir / "providers.yaml").exists()),
        ("config.yaml", (config_dir / "config.yaml").exists()),
    ]

    print(f"  {C.BOLD}📁 Files{C.END}\n")
    for name, exists in checks:
        icon = f"{C.NEON_GREEN}●{C.END}" if exists else f"{C.RED}●{C.END}"
        state = f"{C.NEON_GREEN}Found{C.END}" if exists else f"{C.RED}Missing{C.END}"
        print(f"    {icon} {name}: {state}")
        time.sleep(0.05)

    # API key checks
    env_file = config_dir / ".env"
    if env_file.exists():
        print(f"\n  {C.BOLD}🔑 API Keys{C.END}\n")
        content = env_file.read_text()
        for key, name in [
            ("TELEGRAM_BOT_TOKEN", "Telegram Token"),
            ("GROQ_API_KEY", "Groq API Key"),
            ("OLLAMA_CLOUD_URL", "Ollama Cloud URL"),
            ("OLLAMA_API_KEY", "Ollama API Key"),
        ]:
            has_value = False
            for line in content.splitlines():
                if line.startswith(f"{key}="):
                    value = line.split("=", 1)[1].strip()
                    has_value = bool(value)
                    break
            icon = f"{C.NEON_GREEN}●{C.END}" if has_value else f"{C.NEON_YELLOW}●{C.END}"
            state = (
                f"{C.NEON_GREEN}Configured{C.END}"
                if has_value
                else f"{C.NEON_YELLOW}Not set{C.END}"
            )
            opt = f" {C.DIM}(optional){C.END}" if key != "TELEGRAM_BOT_TOKEN" else ""
            print(f"    {icon} {name}: {state}{opt}")
            time.sleep(0.05)

    # Dependencies
    print(f"\n  {C.BOLD}📦 Dependencies{C.END}\n")
    for pkg, display in [
        ("groq", "groq"),
        ("ollama", "ollama"),
        ("telegram", "python-telegram-bot"),
    ]:
        try:
            __import__(pkg)
            print(f"    {C.NEON_GREEN}●{C.END} {display}: {C.NEON_GREEN}Installed{C.END}")
        except ImportError:
            print(f"    {C.RED}●{C.END} {display}: {C.RED}Not installed{C.END}")
        time.sleep(0.05)

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


def run_tests():
    """Run tests with neon output."""
    clear()
    print_mini_banner()
    print_header("🧪 Running Tests")

    project_dir = get_project_dir()

    progress_bar("Loading test suite", 0.6)
    print()

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=project_dir,
    )

    print()
    if result.returncode == 0:
        success("All tests passed! 🎉")
    else:
        error("Some tests failed")

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


# ═══════════════════════════════════════════════════════════════
# 🚀 Start Bot & Dashboard
# ═══════════════════════════════════════════════════════════════


def start_bot():
    """Start bot with epic neon startup sequence."""
    clear()
    print_mini_banner()
    print_header("🚀 Starting OpenClaw Bot")

    config_ok, env_file = check_config_exists()

    if not config_ok:
        warn("Configuration not found!")
        if confirm("Configure now?"):
            configure_env_interactive()
            return
        else:
            info("Run configuration first.")
            input(f"\n  {C.DARK}Press Enter to continue...{C.END}")
            return

    # Check required values
    env_content = env_file.read_text()

    def _env_has(key):
        for line in env_content.splitlines():
            if line.startswith(f"{key}="):
                return bool(line.split("=", 1)[1].strip())
        return False

    has_telegram = _env_has("TELEGRAM_BOT_TOKEN")
    has_groq = _env_has("GROQ_API_KEY")
    has_ollama = _env_has("OLLAMA_API_KEY")

    missing = []
    if not has_telegram:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not has_groq and not has_ollama:
        missing.append("GROQ_API_KEY or OLLAMA_API_KEY (need at least one)")

    if missing:
        error("Missing required configuration:")
        for key in missing:
            print(f"    {C.RED}\u2717{C.END} {key}")
        if confirm("Configure now?"):
            configure_env_interactive()
            return
        else:
            input(f"\n  {C.DARK}Press Enter to continue...{C.END}")
            return

    # Epic startup sequence
    print()
    progress_bar("Validating configuration", 0.5, 25)
    spinner("Initializing AI providers", 0.4)
    spinner("Loading permissions", 0.3)
    spinner("Connecting to Telegram API", 0.5)
    progress_bar("Starting web dashboard", 0.4, 25)
    spinner("Warming up the lobster", 0.3)

    print()
    pulse_text("🦞 OpenClaw is LIVE!")

    print(
        f"\n  {C.NEON_GREEN}🌐 Dashboard:{C.END} {C.BOLD}{C.NEON_CYAN}http://localhost:8080{C.END}"
    )
    print(f"  {C.DIM}Press Ctrl+C to stop{C.END}")

    print(f"\n  {rainbow_text('━' * 50)}")
    print_credit_line()
    print()

    try:
        from .main import run

        run()
    except KeyboardInterrupt:
        print()
        info("Bot stopped by user")
    except Exception as e:
        error(f"Error: {e}")

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


def start_dashboard_only():
    """Start just the dashboard."""
    clear()
    print_mini_banner()
    print_header("🌐 Starting Dashboard")

    spinner("Initializing dashboard server", 0.5)

    print(
        f"\n  {C.NEON_GREEN}✨ Dashboard URL:{C.END} {C.BOLD}{C.NEON_CYAN}http://localhost:8080{C.END}"
    )
    print(f"  {C.DIM}Press Ctrl+C to stop{C.END}")
    print()

    try:
        from .web.dashboard import DashboardState, run_dashboard

        state = DashboardState()
        state.bot_running = False
        run_dashboard(host="0.0.0.0", port=8080, state=state)
    except KeyboardInterrupt:
        print()
        info("Dashboard stopped by user")
    except Exception as e:
        error(f"Error: {e}")

    input(f"\n  {C.DARK}Press Enter to continue...{C.END}")


# ═══════════════════════════════════════════════════════════════
# 🎬 Main Entry Point
# ═══════════════════════════════════════════════════════════════


def main():
    """Main CLI entry point."""
    # Direct commands
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "start":
            start_bot()
            return
        elif cmd == "config":
            configure_env_interactive()
            return
        elif cmd == "test":
            run_tests()
            return
        elif cmd == "status":
            check_status()
            return

    # Interactive menu loop
    while True:
        choice = show_main_menu()

        if choice == "1":
            start_bot()
        elif choice == "2":
            configure_env_interactive()
        elif choice == "3":
            configure_permissions()
        elif choice == "4":
            check_status()
        elif choice == "5":
            run_tests()
        elif choice == "6":
            start_dashboard_only()
        elif choice.lower() == "q":
            # Epic goodbye
            clear()
            print()
            matrix_rain(2, 60, 0.3)

            goodbye = "Thanks for using OpenClaw! 🦞"
            print(f"\n  {rainbow_text(goodbye)}")

            print(
                f"\n  {C.DIM}Made with {C.END}{C.RED}❤️{C.END}{C.DIM} by {C.END}{C.BOLD}{C.NEON_ORANGE}Sharvinzlife{C.END} {C.GOLD}👑{C.END}"
            )
            print(f"  {C.DARK}├─{C.END} {C.NEON_BLUE}🌐 github.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}├─{C.END} {C.NEON_PINK}📸 instagram.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}├─{C.END} {C.NEON_CYAN}🐦 x.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}└─{C.END} {C.BLUE}📘 fb.com/sharvinzlife{C.END}")

            print(f"\n  {C.DIM}See you next time! {C.END}👋\n")
            break


if __name__ == "__main__":
    main()
