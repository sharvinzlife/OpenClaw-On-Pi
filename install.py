#!/usr/bin/env python3
"""Installer script for OpenClaw Telegram Bot."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


class Installer:
    """Automated installation for OpenClaw Bot."""
    
    MIN_PYTHON_VERSION = (3, 9)
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.venv_dir = self.project_dir / ".venv"
        self.config_dir = self.project_dir / "config"
        self.data_dir = self.project_dir / "data"
        self.logs_dir = self.project_dir / "logs"
    
    def run(self) -> bool:
        """Execute full installation process."""
        print("=" * 50)
        print("OpenClaw Telegram Bot Installer")
        print("=" * 50)
        print()
        
        steps = [
            ("Checking Python version", self.check_python_version),
            ("Creating virtual environment", self.create_venv),
            ("Installing dependencies", self.install_dependencies),
            ("Setting up configuration", self.setup_config_files),
            ("Creating directories", self.create_directories),
        ]
        
        for step_name, step_func in steps:
            print(f"\n→ {step_name}...")
            try:
                if not step_func():
                    print(f"✗ Failed: {step_name}")
                    return False
                print(f"✓ {step_name} complete")
            except Exception as e:
                print(f"✗ Error: {e}")
                return False
        
        # Optional: prompt for secrets
        print("\n→ Configuration...")
        self.prompt_for_secrets()
        
        # Optional: systemd service
        print("\n→ Systemd service...")
        if self.prompt_yes_no("Create systemd service file?"):
            self.create_systemd_service()
        
        print("\n" + "=" * 50)
        print("Installation complete!")
        print("=" * 50)
        print("\nNext steps:")
        print("1. Edit config/.env with your API keys")
        print("2. Edit config/permissions.yaml with allowed user IDs")
        print("3. Run: .venv/bin/python -m src.main")
        print()
        
        return True
    
    def check_python_version(self) -> bool:
        """Verify Python 3.9+ is available."""
        version = sys.version_info[:2]
        
        if version < self.MIN_PYTHON_VERSION:
            print(f"  Python {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}+ required")
            print(f"  Found: Python {version[0]}.{version[1]}")
            return False
        
        print(f"  Python {version[0]}.{version[1]} detected")
        return True
    
    def create_venv(self) -> bool:
        """Create virtual environment."""
        if self.venv_dir.exists():
            print("  Virtual environment already exists")
            return True
        
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(self.venv_dir)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        
        return True
    
    def install_dependencies(self) -> bool:
        """Install required packages."""
        pip_path = self.venv_dir / "bin" / "pip"
        if not pip_path.exists():
            pip_path = self.venv_dir / "Scripts" / "pip.exe"  # Windows
        
        # Upgrade pip first
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            capture_output=True,
        )
        
        # Install package
        result = subprocess.run(
            [str(pip_path), "install", "-e", str(self.project_dir)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        
        return True
    
    def setup_config_files(self) -> bool:
        """Copy template configs."""
        self.config_dir.mkdir(exist_ok=True)
        
        # Copy .env.template to .env if not exists
        env_template = self.config_dir / ".env.template"
        env_file = self.config_dir / ".env"
        
        if env_template.exists() and not env_file.exists():
            shutil.copy(env_template, env_file)
            print("  Created config/.env from template")
        
        return True
    
    def create_directories(self) -> bool:
        """Create required directories."""
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        return True
    
    def prompt_for_secrets(self) -> dict:
        """Interactively prompt user for API keys."""
        env_file = self.config_dir / ".env"
        
        if not env_file.exists():
            print("  No .env file found, skipping")
            return {}
        
        print("\n  You can configure API keys now or edit config/.env later.")
        
        if not self.prompt_yes_no("  Configure API keys now?"):
            return {}
        
        secrets = {}
        
        # Telegram token
        token = input("  Telegram Bot Token: ").strip()
        if token:
            secrets["TELEGRAM_BOT_TOKEN"] = token
        
        # Groq API key
        groq_key = input("  Groq API Key: ").strip()
        if groq_key:
            secrets["GROQ_API_KEY"] = groq_key
        
        # Ollama Cloud URL (optional)
        ollama_url = input("  Ollama Cloud URL (optional): ").strip()
        if ollama_url:
            secrets["OLLAMA_CLOUD_URL"] = ollama_url
        
        # Update .env file
        if secrets:
            self._update_env_file(env_file, secrets)
            print("  Updated config/.env")
        
        return secrets
    
    def _update_env_file(self, env_file: Path, secrets: dict) -> None:
        """Update .env file with secrets."""
        lines = env_file.read_text().splitlines()
        
        for key, value in secrets.items():
            # Find and replace existing line
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    found = True
                    break
            
            if not found:
                lines.append(f"{key}={value}")
        
        env_file.write_text("\n".join(lines) + "\n")
    
    def create_systemd_service(self) -> bool:
        """Generate systemd service file."""
        service_content = f"""[Unit]
Description=OpenClaw AI Telegram Bot
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'root')}
WorkingDirectory={self.project_dir}
ExecStart={self.venv_dir}/bin/python -m src.main
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.project_dir / "scripts" / "openclaw-bot.service"
        service_file.parent.mkdir(exist_ok=True)
        service_file.write_text(service_content)
        
        print(f"  Created {service_file}")
        print("  To install: sudo cp scripts/openclaw-bot.service /etc/systemd/system/")
        print("  To enable: sudo systemctl enable openclaw-bot")
        print("  To start: sudo systemctl start openclaw-bot")
        
        return True
    
    def prompt_yes_no(self, question: str) -> bool:
        """Prompt user for yes/no answer."""
        while True:
            answer = input(f"{question} [y/n]: ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False


def main():
    """Run installer."""
    # Determine project directory
    script_dir = Path(__file__).parent.resolve()
    
    installer = Installer(str(script_dir))
    success = installer.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
