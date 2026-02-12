"""Skill registry — discovers, loads, and manages skill lifecycle."""

import importlib
import inspect
import logging
import pkgutil
from datetime import datetime
from typing import Optional

from .base_skill import BaseSkill, SkillResult, SkillStats

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Discovers, loads, and manages skill lifecycle.

    Scans the skills directory for BaseSkill subclasses, checks dependencies
    and config, then registers enabled skills with the CommandRouter.
    """

    def __init__(self, skills_config: dict, command_router):
        """Initialize the registry.

        Args:
            skills_config: The 'skills' section from skills.yaml.
            command_router: CommandRouter instance to register commands with.
        """
        self.config = skills_config
        self.router = command_router
        self.skills: dict[str, BaseSkill] = {}
        self.stats: dict[str, SkillStats] = {}

    def discover_and_load(self) -> None:
        """Scan skills/ directory, import modules, instantiate and register.

        For each module in the skills package:
        1. Import the module
        2. Find BaseSkill subclasses
        3. Check dependencies via check_dependencies()
        4. Check if enabled in config
        5. Instantiate with skill-specific config
        6. Register command with the CommandRouter
        """
        import src.skills as skills_package

        package_path = skills_package.__path__
        package_name = skills_package.__name__

        for importer, module_name, is_pkg in pkgutil.iter_modules(package_path):
            # Skip internal modules
            if module_name.startswith("_") or module_name in ("base_skill", "registry"):
                continue

            full_module_name = f"{package_name}.{module_name}"

            try:
                module = importlib.import_module(full_module_name)
            except Exception as e:
                logger.warning(f"Failed to import skill module '{module_name}': {e}")
                continue

            # Find all BaseSkill subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseSkill)
                    and attr is not BaseSkill
                    and not inspect.isabstract(attr)
                ):
                    self._try_load_skill(attr)

    def _try_load_skill(self, skill_class: type[BaseSkill]) -> None:
        """Attempt to load and register a single skill class.

        Args:
            skill_class: A concrete BaseSkill subclass.
        """
        skill_name = skill_class.name
        command = skill_class.command

        if not skill_name or not command:
            logger.warning(
                f"Skill class {skill_class.__name__} missing name or command, skipping"
            )
            return

        # Check dependencies
        try:
            if not skill_class.check_dependencies():
                logger.warning(
                    f"Skill '{skill_name}' missing dependencies, skipping"
                )
                return
        except Exception as e:
            logger.warning(
                f"Skill '{skill_name}' dependency check failed: {e}, skipping"
            )
            return

        # Get skill-specific config (default to enabled: true if not in config)
        skill_config = self.config.get(skill_name, {"enabled": True})

        # Check if disabled in config
        if not skill_config.get("enabled", True):
            logger.info(f"Skill '{skill_name}' disabled in config, skipping")
            return

        # Instantiate the skill
        try:
            skill_instance = skill_class(skill_config)
        except Exception as e:
            logger.warning(f"Failed to instantiate skill '{skill_name}': {e}")
            return

        # Register with router
        self.skills[command] = skill_instance
        self.stats[command] = SkillStats(name=skill_name)

        # Create a handler closure that routes through execute_skill.
        # Use a default argument to capture the current command value.
        async def handler(
            user_id: int, args: list[str], _cmd=command, **kwargs
        ) -> str:
            result = await self.execute_skill(_cmd, user_id, args, **kwargs)
            if result.error:
                return f"❌ {result.error}"
            if result.text:
                return result.text
            return "✅ Done (no output)"

        self.router.register(
            command=command,
            handler=handler,
            permission_level=skill_class.permission_level,
            description=skill_class.description,
        )

        logger.info(
            f"Loaded skill '{skill_name}' -> /{command} "
            f"(permission: {skill_class.permission_level})"
        )

    def get_skill(self, command: str) -> Optional[BaseSkill]:
        """Get a loaded skill by command name.

        Args:
            command: The command string (without /).

        Returns:
            The skill instance, or None if not found.
        """
        return self.skills.get(command)

    async def execute_skill(
        self, command: str, user_id: int, args: list[str], **kwargs
    ) -> SkillResult:
        """Execute a skill, track stats, handle errors.

        Args:
            command: The command string (without /).
            user_id: Telegram user ID.
            args: Command arguments.
            **kwargs: Extra context.

        Returns:
            SkillResult with text, file_path, or error.
        """
        skill = self.skills.get(command)
        if not skill:
            return SkillResult(error=f"Unknown skill: {command}")

        stats = self.stats[command]
        stats.total_executions += 1
        stats.last_used = datetime.now()

        try:
            result = await skill.execute(user_id, args, **kwargs)
            if result.error:
                stats.failure_count += 1
            else:
                stats.success_count += 1
            return result
        except Exception as e:
            stats.failure_count += 1
            logger.error(f"Skill '{skill.name}' raised exception: {e}")
            return SkillResult(error=str(e))

    def get_all_stats(self) -> dict[str, SkillStats]:
        """Get stats for all loaded skills.

        Returns:
            Dict mapping command to SkillStats.
        """
        return dict(self.stats)
