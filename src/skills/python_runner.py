"""Python runner skill — execute Python code in a sandboxed subprocess."""

import subprocess
import sys
import textwrap

from src.skills.base_skill import BaseSkill, SkillResult

BLOCKED_MODULES = {"os", "sys", "subprocess", "shutil", "pathlib", "socket"}
BLOCKED_BUILTINS = {"exec", "eval", "compile", "open", "__import__", "breakpoint"}

# Sandbox wrapper template — injected before user code
_SANDBOX_TEMPLATE = textwrap.dedent("""\
    import sys

    # --- Import blocker ---
    class ImportBlocker:
        BLOCKED = {blocked_modules}

        def find_module(self, fullname, path=None):
            if fullname.split(".")[0] in self.BLOCKED:
                return self

        def load_module(self, fullname):
            raise ImportError(f"Module '{{fullname}}' is blocked in sandbox")

    sys.meta_path.insert(0, ImportBlocker())

    # --- Remove dangerous builtins ---
    import builtins as _builtins
    for _name in {blocked_builtins}:
        if hasattr(_builtins, _name):
            delattr(_builtins, _name)

    # --- User code ---
    {user_code}
""")


def _build_sandbox_code(user_code: str) -> str:
    """Build the full sandbox wrapper around user code.

    Args:
        user_code: The raw Python code from the user.

    Returns:
        A string containing the sandbox setup + user code.
    """
    # Indent user code to sit inside the template cleanly
    indented = textwrap.indent(user_code, "")
    return _SANDBOX_TEMPLATE.format(
        blocked_modules=repr(BLOCKED_MODULES),
        blocked_builtins=repr(BLOCKED_BUILTINS),
        user_code=indented,
    )


class PythonRunnerSkill(BaseSkill):
    """Execute Python code in a sandboxed subprocess (admin only)."""

    name = "python_runner"
    command = "run"
    description = "Execute Python code (admin only)"
    permission_level = "admin"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        """Run user-provided Python code in a sandboxed subprocess.

        Args:
            user_id: Telegram user ID.
            args: Command arguments — joined into a code string.

        Returns:
            SkillResult with stdout/stderr output or an error message.
        """
        code = " ".join(args).strip()
        if not code:
            return SkillResult(error="Usage: /run <python code>")

        sandbox_code = _build_sandbox_code(code)

        try:
            result = subprocess.run(
                [sys.executable, "-c", sandbox_code],
                timeout=10,
                capture_output=True,
                text=True,
            )
            output = (result.stdout + result.stderr).strip()
            if not output:
                return SkillResult(text="✅ Code executed successfully (no output)")
            return SkillResult(text=output)
        except subprocess.TimeoutExpired:
            return SkillResult(error="⏱️ Code execution timed out (10s limit)")

    @classmethod
    def check_dependencies(cls) -> bool:
        """No external dependencies needed."""
        return True
