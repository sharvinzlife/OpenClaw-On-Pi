#!/usr/bin/env python3
"""Professional CLI for OpenClaw Telegram Bot."""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Emojis
EMOJI = {
    'robot': '🤖',
    'rocket': '🚀',
    'check': '✅',
    'cross': '❌',
    'warning': '⚠️',
    'gear': '⚙️',
    'key': '🔑',
    'lock': '🔒',
    'folder': '📁',
    'file': '📄',
    'edit': '✏️',
    'sparkles': '✨',
    'lightning': '⚡',
    'wave': '👋',
    'star': '⭐',
    'fire': '🔥',
    'package': '📦',
    'link': '🔗',
    'info': 'ℹ️',
    'arrow': '➜',
    'dot': '•',
    'brain': '🧠',
    'cloud': '☁️',
    'server': '🖥️',
}


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print the OpenClaw banner."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
   ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗
  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██║     ██╔══██╗██║    ██║
  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║     ███████║██║ █╗ ██║
  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║     ██╔══██║██║███╗██║
  ╚██████╔╝██║     ███████╗██║ ╚████║╚██████╗███████╗██║  ██║╚███╔███╔╝
   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
{Colors.END}
{Colors.DIM}                    AI-Powered Telegram Bot{Colors.END}
{Colors.YELLOW}        {EMOJI['brain']} Groq  {EMOJI['cloud']} Ollama Cloud  {EMOJI['server']} Local Ollama{Colors.END}
"""
    print(banner)


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'═' * 60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'═' * 60}{Colors.END}\n")


def print_step(step: int, total: int, text: str):
    """Print a step indicator."""
    print(f"{Colors.BLUE}[{step}/{total}]{Colors.END} {EMOJI['arrow']} {text}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}{EMOJI['check']} {text}{Colors.END}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}{EMOJI['cross']} {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}{EMOJI['warning']} {text}{Colors.END}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.DIM}{EMOJI['info']} {text}{Colors.END}")


def print_menu_item(key: str, text: str, emoji: str = ''):
    """Print a menu item."""
    emoji_str = f"{emoji} " if emoji else ""
    print(f"  {Colors.CYAN}[{key}]{Colors.END} {emoji_str}{text}")


def get_input(prompt: str, default: str = "") -> str:
    """Get user input with styled prompt."""
    default_str = f" {Colors.DIM}({default}){Colors.END}" if default else ""
    try:
        value = input(f"{Colors.YELLOW}{EMOJI['arrow']}{Colors.END} {prompt}{default_str}: ").strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def confirm(prompt: str, default: bool = True) -> bool:
    """Get yes/no confirmation."""
    default_str = "Y/n" if default else "y/N"
    try:
        value = input(f"{Colors.YELLOW}{EMOJI['arrow']}{Colors.END} {prompt} [{default_str}]: ").strip().lower()
        if not value:
            return default
        return value in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def get_project_dir() -> Path:
    """Get the project directory."""
    return Path(__file__).parent.parent.resolve()


def check_config_exists() -> tuple[bool, Path]:
    """Check if config exists and return path."""
    project_dir = get_project_dir()
    config_dir = project_dir / "config"
    env_file = config_dir / ".env"
    return env_file.exists(), env_file


def show_main_menu():
    """Show the main menu."""
    clear_screen()
    print_banner()
    
    print(f"\n{Colors.BOLD}  What would you like to do?{Colors.END}\n")
    print_menu_item("1", "Start the bot", EMOJI['rocket'])
    print_menu_item("2", "Configure API keys", EMOJI['key'])
    print_menu_item("3", "Edit permissions", EMOJI['lock'])
    print_menu_item("4", "Check status", EMOJI['gear'])
    print_menu_item("5", "Run tests", EMOJI['check'])
    print_menu_item("6", "Start dashboard only", EMOJI['link'])
    print_menu_item("q", "Quit", "")
    print()
    
    return get_input("Select option", "1")


def configure_env_interactive():
    """Interactive environment configuration."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['key']} API Key Configuration")
    
    project_dir = get_project_dir()
    config_dir = project_dir / "config"
    env_file = config_dir / ".env"
    
    print(f"{EMOJI['folder']} Config location: {Colors.CYAN}{config_dir}{Colors.END}")
    print(f"{EMOJI['file']} Env file: {Colors.CYAN}{env_file}{Colors.END}")
    print()
    
    # Check if .env exists
    if not env_file.exists():
        template = config_dir / ".env.template"
        if template.exists():
            shutil.copy(template, env_file)
            print_success("Created .env from template")
        else:
            env_file.touch()
            print_success("Created new .env file")
    
    print(f"\n{Colors.BOLD}Choose configuration method:{Colors.END}\n")
    print_menu_item("1", "Paste values directly (recommended)", EMOJI['lightning'])
    print_menu_item("2", "Open in nano editor", EMOJI['edit'])
    print_menu_item("3", "Open in vim editor", EMOJI['edit'])
    print_menu_item("4", "Show current values", EMOJI['info'])
    print_menu_item("b", "Back to main menu", "")
    print()
    
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
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def configure_paste_mode(env_file: Path):
    """Configure by pasting values."""
    print(f"\n{Colors.BOLD}{EMOJI['sparkles']} Quick Configuration{Colors.END}\n")
    
    print(f"{Colors.DIM}Enter your API keys below. Press Enter to skip.{Colors.END}\n")
    
    # Load existing values
    existing = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, _, value = line.partition('=')
                existing[key.strip()] = value.strip()
    
    # Telegram Token
    print(f"\n{EMOJI['robot']} {Colors.BOLD}Telegram Bot Token{Colors.END}")
    print(f"{Colors.DIM}   Get from @BotFather on Telegram{Colors.END}")
    current = existing.get('TELEGRAM_BOT_TOKEN', '')
    masked = f"{current[:10]}...{current[-5:]}" if len(current) > 20 else current
    if masked:
        print(f"{Colors.DIM}   Current: {masked}{Colors.END}")
    telegram_token = get_input("Token")
    if telegram_token:
        existing['TELEGRAM_BOT_TOKEN'] = telegram_token
    
    # Groq API Key
    print(f"\n{EMOJI['brain']} {Colors.BOLD}Groq API Key{Colors.END}")
    print(f"{Colors.DIM}   Get from console.groq.com{Colors.END}")
    current = existing.get('GROQ_API_KEY', '')
    masked = f"{current[:10]}...{current[-5:]}" if len(current) > 20 else current
    if masked:
        print(f"{Colors.DIM}   Current: {masked}{Colors.END}")
    groq_key = get_input("API Key")
    if groq_key:
        existing['GROQ_API_KEY'] = groq_key
    
    # Ollama Cloud URL (optional)
    print(f"\n{EMOJI['cloud']} {Colors.BOLD}Ollama Cloud URL{Colors.END} {Colors.DIM}(optional){Colors.END}")
    print(f"{Colors.DIM}   Your remote Ollama instance URL{Colors.END}")
    current = existing.get('OLLAMA_CLOUD_URL', '')
    if current:
        print(f"{Colors.DIM}   Current: {current}{Colors.END}")
    ollama_url = get_input("URL")
    if ollama_url:
        existing['OLLAMA_CLOUD_URL'] = ollama_url
    
    # Write to file
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
    print()
    print_success("Configuration saved!")


def open_editor(file_path: Path, editor: str):
    """Open file in specified editor."""
    print(f"\n{EMOJI['edit']} Opening {file_path.name} in {editor}...")
    print(f"{Colors.DIM}   File: {file_path}{Colors.END}")
    print(f"{Colors.DIM}   Save and exit when done.{Colors.END}\n")
    
    if not shutil.which(editor):
        print_error(f"{editor} not found. Install it or use another option.")
        return
    
    subprocess.run([editor, str(file_path)])
    print_success(f"Closed {editor}")


def show_current_config(env_file: Path):
    """Show current configuration (masked)."""
    print(f"\n{EMOJI['file']} {Colors.BOLD}Current Configuration{Colors.END}\n")
    
    if not env_file.exists():
        print_warning("No .env file found")
        return
    
    for line in env_file.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            
            if value and len(value) > 10:
                masked = f"{value[:5]}{'*' * 10}{value[-3:]}"
            elif value:
                masked = '*' * len(value)
            else:
                masked = f"{Colors.DIM}(not set){Colors.END}"
            
            status = EMOJI['check'] if value else EMOJI['cross']
            print(f"  {status} {Colors.CYAN}{key}{Colors.END}: {masked}")


def configure_permissions():
    """Configure user permissions."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['lock']} User Permissions")
    
    project_dir = get_project_dir()
    permissions_file = project_dir / "config" / "permissions.yaml"
    
    print(f"{EMOJI['file']} File: {Colors.CYAN}{permissions_file}{Colors.END}")
    print()
    
    print(f"{Colors.BOLD}How to get your Telegram User ID:{Colors.END}")
    print(f"  1. Message @userinfobot on Telegram")
    print(f"  2. It will reply with your user ID")
    print()
    
    print(f"{Colors.BOLD}Choose option:{Colors.END}\n")
    print_menu_item("1", "Add admin user ID", EMOJI['star'])
    print_menu_item("2", "Open in nano", EMOJI['edit'])
    print_menu_item("3", "Open in vim", EMOJI['edit'])
    print_menu_item("b", "Back", "")
    print()
    
    choice = get_input("Select option", "1")
    
    if choice == "1":
        user_id = get_input("Enter your Telegram User ID")
        if user_id and user_id.isdigit():
            # Read current file
            content = permissions_file.read_text() if permissions_file.exists() else ""
            
            # Add user ID to admins section
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
                print_success(f"Added user {user_id} as admin")
            else:
                print_info(f"User {user_id} already in config")
    elif choice == "2":
        open_editor(permissions_file, "nano")
    elif choice == "3":
        open_editor(permissions_file, "vim")
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def check_status():
    """Check bot configuration status."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['gear']} Configuration Status")
    
    project_dir = get_project_dir()
    config_dir = project_dir / "config"
    
    checks = [
        ("Config directory", config_dir.exists()),
        (".env file", (config_dir / ".env").exists()),
        ("permissions.yaml", (config_dir / "permissions.yaml").exists()),
        ("providers.yaml", (config_dir / "providers.yaml").exists()),
        ("config.yaml", (config_dir / "config.yaml").exists()),
    ]
    
    print(f"{Colors.BOLD}Files:{Colors.END}\n")
    for name, exists in checks:
        status = EMOJI['check'] if exists else EMOJI['cross']
        color = Colors.GREEN if exists else Colors.RED
        print(f"  {status} {name}: {color}{'Found' if exists else 'Missing'}{Colors.END}")
    
    # Check env values
    env_file = config_dir / ".env"
    if env_file.exists():
        print(f"\n{Colors.BOLD}API Keys:{Colors.END}\n")
        
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
            
            status = EMOJI['check'] if has_value else EMOJI['cross']
            color = Colors.GREEN if has_value else Colors.YELLOW
            state = "Configured" if has_value else "Not set"
            optional = " (optional)" if key == "OLLAMA_CLOUD_URL" else ""
            print(f"  {status} {name}: {color}{state}{Colors.END}{Colors.DIM}{optional}{Colors.END}")
    
    # Check Python packages
    print(f"\n{Colors.BOLD}Dependencies:{Colors.END}\n")
    
    try:
        import groq
        print(f"  {EMOJI['check']} groq: {Colors.GREEN}Installed{Colors.END}")
    except ImportError:
        print(f"  {EMOJI['cross']} groq: {Colors.RED}Not installed{Colors.END}")
    
    try:
        import ollama
        print(f"  {EMOJI['check']} ollama: {Colors.GREEN}Installed{Colors.END}")
    except ImportError:
        print(f"  {EMOJI['cross']} ollama: {Colors.RED}Not installed{Colors.END}")
    
    try:
        import telegram
        print(f"  {EMOJI['check']} python-telegram-bot: {Colors.GREEN}Installed{Colors.END}")
    except ImportError:
        print(f"  {EMOJI['cross']} python-telegram-bot: {Colors.RED}Not installed{Colors.END}")
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def run_tests():
    """Run the test suite."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['check']} Running Tests")
    
    project_dir = get_project_dir()
    
    print(f"{EMOJI['lightning']} Running property-based tests...\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=project_dir,
    )
    
    if result.returncode == 0:
        print()
        print_success("All tests passed!")
    else:
        print()
        print_error("Some tests failed")
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def start_bot():
    """Start the bot."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['rocket']} Starting OpenClaw Bot")
    
    # Check configuration
    config_ok, env_file = check_config_exists()
    
    if not config_ok:
        print_warning("Configuration not found!")
        print()
        if confirm("Would you like to configure now?"):
            configure_env_interactive()
            return
        else:
            print_info("Run configuration first before starting the bot.")
            input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")
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
        print_error("Missing required configuration:")
        for key in missing:
            print(f"  {EMOJI['cross']} {key}")
        print()
        if confirm("Would you like to configure now?"):
            configure_env_interactive()
            return
        else:
            input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")
            return
    
    print_success("Configuration OK")
    print()
    print(f"{EMOJI['robot']} Starting bot...")
    print(f"{EMOJI['link']} Dashboard: {Colors.CYAN}http://localhost:8080{Colors.END}")
    print(f"{Colors.DIM}Press Ctrl+C to stop{Colors.END}")
    print()
    
    # Import and run
    try:
        from .main import run
        run()
    except KeyboardInterrupt:
        print()
        print_info("Bot stopped by user")
    except Exception as e:
        print_error(f"Error: {e}")
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def start_dashboard_only():
    """Start just the dashboard for testing."""
    clear_screen()
    print_banner()
    print_header(f"{EMOJI['link']} Starting Dashboard")
    
    print(f"{EMOJI['sparkles']} Dashboard URL: {Colors.CYAN}http://localhost:8080{Colors.END}")
    print(f"{Colors.DIM}Press Ctrl+C to stop{Colors.END}")
    print()
    
    try:
        from .web.dashboard import run_dashboard, DashboardState
        state = DashboardState()
        state.bot_running = False  # Bot not running, just dashboard
        run_dashboard(host='0.0.0.0', port=8080, state=state)
    except KeyboardInterrupt:
        print()
        print_info("Dashboard stopped by user")
    except Exception as e:
        print_error(f"Error: {e}")
    
    input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")


def main():
    """Main CLI entry point."""
    # Handle direct commands
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
            input(f"\n{Colors.DIM}Press Enter to exit...{Colors.END}")
            return
    
    # Interactive menu
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
            clear_screen()
            print(f"\n{EMOJI['wave']} Goodbye!\n")
            break


if __name__ == "__main__":
    main()
