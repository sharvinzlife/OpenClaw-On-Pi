#!/usr/bin/env python3
"""Epic Neon CLI for OpenClaw Telegram Bot - Made with ❤️ by Sharvinzlife 👑"""

import os
import sys
import subprocess
import shutil
import time
import random
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 🎨 NEON ANSI Colors & Styles
# ═══════════════════════════════════════════════════════════════

class C:
    """Neon color codes."""
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'
    # Neon palette
    RED = '\033[38;5;196m'
    GREEN = '\033[38;5;46m'
    YELLOW = '\033[38;5;226m'
    BLUE = '\033[38;5;33m'
    CYAN = '\033[38;5;51m'
    MAGENTA = '\033[38;5;201m'
    ORANGE = '\033[38;5;208m'
    CORAL = '\033[38;5;209m'
    SALMON = '\033[38;5;210m'
    PEACH = '\033[38;5;216m'
    GOLD = '\033[38;5;220m'
    AMBER = '\033[38;5;214m'
    PINK = '\033[38;5;213m'
    LAVENDER = '\033[38;5;183m'
    SKY = '\033[38;5;117m'
    MINT = '\033[38;5;121m'
    LIME = '\033[38;5;154m'
    PURPLE = '\033[38;5;135m'
    NEON_GREEN = '\033[38;5;118m'
    NEON_PINK = '\033[38;5;199m'
    NEON_BLUE = '\033[38;5;39m'
    NEON_CYAN = '\033[38;5;87m'
    NEON_ORANGE = '\033[38;5;202m'
    NEON_YELLOW = '\033[38;5;227m'
    WHITE = '\033[38;5;255m'
    GRAY = '\033[38;5;245m'
    DARK = '\033[38;5;238m'

NEON = [C.NEON_PINK, C.NEON_ORANGE, C.NEON_YELLOW, C.NEON_GREEN, C.NEON_CYAN, C.NEON_BLUE, C.MAGENTA]
WARM = [C.PEACH, C.SALMON, C.CORAL, C.ORANGE, C.AMBER, C.GOLD]
FIRE = [C.RED, C.NEON_ORANGE, C.ORANGE, C.AMBER, C.GOLD, C.NEON_YELLOW]


# ═══════════════════════════════════════════════════════════════
# ✨ Animation Engine
# ═══════════════════════════════════════════════════════════════

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


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
    return ''.join(result)


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
    frames = ['◜', '◠', '◝', '◞', '◡', '◟']
    colors = [C.NEON_PINK, C.NEON_ORANGE, C.NEON_YELLOW, C.NEON_GREEN, C.NEON_CYAN, C.NEON_BLUE]
    end = time.time() + duration
    i = 0
    while time.time() < end:
        c = colors[i % len(colors)]
        f = frames[i % len(frames)]
        sys.stdout.write(f'\r  {c}{C.BOLD}{f}{C.END} {msg}')
        sys.stdout.flush()
        time.sleep(0.07)
        i += 1
    sys.stdout.write(f'\r  {C.NEON_GREEN}{C.BOLD}✓{C.END} {msg}\n')
    sys.stdout.flush()


def progress_bar(msg: str, duration: float = 1.0, width: int = 30):
    """Animated neon progress bar."""
    steps = width
    for i in range(steps + 1):
        pct = i / steps
        filled = int(width * pct)
        # Gradient fill
        bar = ''
        for j in range(filled):
            bar += f"{NEON[j % len(NEON)]}█"
        bar += f"{C.DARK}{'░' * (width - filled)}"
        sys.stdout.write(f'\r  {C.GRAY}[{bar}{C.GRAY}]{C.END} {C.WHITE}{int(pct*100):3d}%{C.END} {msg}')
        sys.stdout.flush()
        time.sleep(duration / steps)
    sys.stdout.write(f'\r  {C.NEON_GREEN}{C.BOLD}[{"█" * width}] 100%{C.END} {msg}\n')
    sys.stdout.flush()


def matrix_rain(lines: int = 3, width: int = 60, duration: float = 0.8):
    """Quick matrix-style rain effect."""
    chars = '01アイウエオカキクケコサシスセソ🦞'
    end = time.time() + duration
    while time.time() < end:
        line = ''
        for _ in range(width):
            if random.random() < 0.3:
                c = random.choice([C.NEON_GREEN, C.MINT, C.LIME, C.GREEN])
                line += f"{c}{random.choice(chars)}"
            else:
                line += ' '
        print(f"  {line}{C.END}")
        time.sleep(0.06)


def pulse_text(text: str, cycles: int = 2):
    """Pulse text between bright and dim."""
    for _ in range(cycles):
        sys.stdout.write(f'\r  {C.BOLD}{C.NEON_ORANGE}{text}{C.END}')
        sys.stdout.flush()
        time.sleep(0.15)
        sys.stdout.write(f'\r  {C.DIM}{C.ORANGE}{text}{C.END}')
        sys.stdout.flush()
        time.sleep(0.15)
    sys.stdout.write(f'\r  {C.BOLD}{C.NEON_ORANGE}{text}{C.END}\n')
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
    print(f"\n  {neon_glow('🧠 Groq', C.NEON_CYAN)}  {C.DARK}│{C.END}  {neon_glow('☁️  Ollama Cloud', C.NEON_GREEN)}  {C.DARK}│{C.END}  {neon_glow('🖥️  Local Ollama', C.NEON_ORANGE)}")
    
    # Neon separator
    sep = '━' * 62
    print(f"\n  {rainbow_text(sep)}")
    
    # Branding footer
    print_credit_line()


def print_credit_line():
    """Print the credit/social line."""
    print(f"\n  {C.DIM}Made with {C.END}{C.RED}❤️{C.END}{C.DIM} by {C.END}{C.BOLD}{C.NEON_ORANGE}Sharvinzlife{C.END} {C.GOLD}👑{C.END}")
    print(f"  {C.DARK}├─{C.END} {C.NEON_BLUE}🌐 github.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}├─{C.END} {C.NEON_PINK}📸 instagram.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}├─{C.END} {C.NEON_CYAN}🐦 x.com/sharvinzlife{C.END}")
    print(f"  {C.DARK}└─{C.END} {C.BLUE}📘 fb.com/sharvinzlife{C.END}")


def print_header(text: str):
    """Neon section header."""
    sep = '═' * 58
    print(f"\n  {C.NEON_ORANGE}{C.BOLD}{sep}{C.END}")
    typewriter(f"  {C.BOLD}{C.NEON_ORANGE}  {text}{C.END}", 0.01)
    print(f"  {C.NEON_ORANGE}{C.BOLD}{sep}{C.END}\n")


def print_mini_banner():
    """Smaller banner for sub-screens."""
    print(f"\n  {C.BOLD}{C.NEON_ORANGE}🦞 OpenClaw{C.END} {C.DARK}│{C.END} {C.DIM}AI Telegram Bot{C.END} {C.DARK}│{C.END} {C.DIM}Made with {C.RED}❤️{C.END}{C.DIM} by {C.NEON_ORANGE}Sharvinzlife {C.GOLD}👑{C.END}")
    print(f"  {C.DARK}{'─' * 62}{C.END}")


# ═══════════════════════════════════════════════════════════════
# 🎮 UI Components
# ═══════════════════════════════════════════════════════════════

def menu_item(key: str, text: str, emoji: str = '', color=None):
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
        return val in ('y', 'yes')
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
        ("1", "Start the bot",          "🚀", C.NEON_GREEN),
        ("2", "Configure API keys",     "🔑", C.NEON_YELLOW),
        ("3", "Edit permissions",       "🔒", C.NEON_ORANGE),
        ("4", "Check status",           "⚙️",  C.NEON_CYAN),
        ("5", "Run tests",              "🧪", C.NEON_BLUE),
        ("6", "Start dashboard only",   "🌐", C.NEON_PINK),
        ("q", "Quit",                   "👋", C.DARK),
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


def configure_paste_mode(env_file: Path):
    """Paste-mode config with neon prompts."""
    print(f"\n  {C.BOLD}{C.NEON_ORANGE}✨ Quick Configuration{C.END}")
    print(f"  {C.DIM}Enter your API keys. Press Enter to skip.{C.END}\n")
    
    existing = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, _, value = line.partition('=')
                existing[key.strip()] = value.strip()
    
    # Telegram Token
    print(f"\n  {C.NEON_ORANGE}🦞 Telegram Bot Token{C.END}")
    print(f"  {C.DIM}   Get from @BotFather on Telegram{C.END}")
    cur = existing.get('TELEGRAM_BOT_TOKEN', '')
    if cur and len(cur) > 20:
        print(f"  {C.DIM}   Current: {cur[:10]}...{cur[-5:]}{C.END}")
    token = get_input("Token")
    if token:
        existing['TELEGRAM_BOT_TOKEN'] = token
    
    # Groq API Key
    print(f"\n  {C.NEON_CYAN}🧠 Groq API Key{C.END}")
    print(f"  {C.DIM}   Get from console.groq.com{C.END}")
    cur = existing.get('GROQ_API_KEY', '')
    if cur and len(cur) > 20:
        print(f"  {C.DIM}   Current: {cur[:10]}...{cur[-5:]}{C.END}")
    groq_key = get_input("API Key")
    if groq_key:
        existing['GROQ_API_KEY'] = groq_key
    
    # Ollama Cloud URL
    print(f"\n  {C.NEON_GREEN}☁️  Ollama Cloud URL{C.END} {C.DIM}(optional){C.END}")
    print(f"  {C.DIM}   Your remote Ollama instance URL{C.END}")
    cur = existing.get('OLLAMA_CLOUD_URL', '')
    if cur:
        print(f"  {C.DIM}   Current: {cur}{C.END}")
    ollama_url = get_input("URL")
    if ollama_url:
        existing['OLLAMA_CLOUD_URL'] = ollama_url
    
    print()
    spinner("Saving configuration", 0.5)
    
    lines = [
        "# OpenClaw Telegram Bot - Environment Configuration",
        "",
        "# Telegram Bot Token from @BotFather",
        f"TELEGRAM_BOT_TOKEN={existing.get('TELEGRAM_BOT_TOKEN', '')}",
        "",
        "# Groq API Key from console.groq.com",
        f"GROQ_API_KEY={existing.get('GROQ_API_KEY', '')}",
        "",
        "# Ollama Cloud URL (optional)",
        f"OLLAMA_CLOUD_URL={existing.get('OLLAMA_CLOUD_URL', '')}",
    ]
    env_file.write_text('\n'.join(lines) + '\n')
    success("Configuration saved!")
    
    # Admin setup
    print(f"\n  {C.NEON_YELLOW}🔒 Admin Access Setup{C.END}")
    print(f"  {C.DIM}   Get your Telegram User ID from @userinfobot{C.END}")
    
    project_dir = get_project_dir()
    permissions_file = project_dir / "config" / "permissions.yaml"
    
    admin_exists = False
    if permissions_file.exists():
        content = permissions_file.read_text()
        in_admins = False
        for line in content.splitlines():
            if line.strip() == "admins:":
                in_admins = True
            elif in_admins and line.strip().startswith("- ") and not line.strip().startswith("# "):
                admin_exists = True
                break
            elif in_admins and not line.startswith(" ") and not line.startswith("\t"):
                in_admins = False
    
    if admin_exists:
        info("Admin already configured")
        if confirm("Add another admin?", default=False):
            setup_admin_user(permissions_file)
    else:
        if confirm("Set up admin access now?", default=True):
            setup_admin_user(permissions_file)


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
    
    permissions_file.write_text('\n'.join(new_lines) + '\n')
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
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip()
            if value and len(value) > 10:
                masked = f"{value[:5]}{'*' * 10}{value[-3:]}"
            elif value:
                masked = '*' * len(value)
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
                permissions_file.write_text('\n'.join(new_lines) + '\n')
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
        ]:
            has_value = False
            for line in content.splitlines():
                if line.startswith(f"{key}="):
                    value = line.split('=', 1)[1].strip()
                    has_value = bool(value)
                    break
            icon = f"{C.NEON_GREEN}●{C.END}" if has_value else f"{C.NEON_YELLOW}●{C.END}"
            state = f"{C.NEON_GREEN}Configured{C.END}" if has_value else f"{C.NEON_YELLOW}Not set{C.END}"
            opt = f" {C.DIM}(optional){C.END}" if key == "OLLAMA_CLOUD_URL" else ""
            print(f"    {icon} {name}: {state}{opt}")
            time.sleep(0.05)
    
    # Dependencies
    print(f"\n  {C.BOLD}📦 Dependencies{C.END}\n")
    for pkg, display in [("groq", "groq"), ("ollama", "ollama"), ("telegram", "python-telegram-bot")]:
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
    content = env_file.read_text()
    missing = []
    for key in ["TELEGRAM_BOT_TOKEN", "GROQ_API_KEY"]:
        has_value = False
        for line in content.splitlines():
            if line.startswith(f"{key}="):
                value = line.split('=', 1)[1].strip()
                has_value = bool(value)
                break
        if not has_value:
            missing.append(key)
    
    if missing:
        error("Missing required configuration:")
        for key in missing:
            print(f"    {C.RED}✗{C.END} {key}")
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
    
    print(f"\n  {C.NEON_GREEN}🌐 Dashboard:{C.END} {C.BOLD}{C.NEON_CYAN}http://localhost:8080{C.END}")
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
    
    print(f"\n  {C.NEON_GREEN}✨ Dashboard URL:{C.END} {C.BOLD}{C.NEON_CYAN}http://localhost:8080{C.END}")
    print(f"  {C.DIM}Press Ctrl+C to stop{C.END}")
    print()
    
    try:
        from .web.dashboard import run_dashboard, DashboardState
        state = DashboardState()
        state.bot_running = False
        run_dashboard(host='0.0.0.0', port=8080, state=state)
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
            
            print(f"\n  {C.DIM}Made with {C.END}{C.RED}❤️{C.END}{C.DIM} by {C.END}{C.BOLD}{C.NEON_ORANGE}Sharvinzlife{C.END} {C.GOLD}👑{C.END}")
            print(f"  {C.DARK}├─{C.END} {C.NEON_BLUE}🌐 github.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}├─{C.END} {C.NEON_PINK}📸 instagram.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}├─{C.END} {C.NEON_CYAN}🐦 x.com/sharvinzlife{C.END}")
            print(f"  {C.DARK}└─{C.END} {C.BLUE}📘 fb.com/sharvinzlife{C.END}")
            
            print(f"\n  {C.DIM}See you next time! {C.END}👋\n")
            break


if __name__ == "__main__":
    main()
