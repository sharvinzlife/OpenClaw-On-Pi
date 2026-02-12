"""Unit tests for PythonRunnerSkill."""

import pytest

from src.skills.python_runner import PythonRunnerSkill, _build_sandbox_code


@pytest.fixture
def skill():
    return PythonRunnerSkill(config={"enabled": True})


class TestBuildSandboxCode:
    """Tests for the sandbox code builder."""

    def test_contains_import_blocker(self):
        code = _build_sandbox_code("print('hello')")
        assert "ImportBlocker" in code

    def test_contains_user_code(self):
        code = _build_sandbox_code("print('hello')")
        assert "print('hello')" in code

    def test_blocks_dangerous_builtins(self):
        code = _build_sandbox_code("x = 1")
        assert "exec" in code  # Should be in the blocked set
        assert "eval" in code


class TestPythonRunnerSkillExecute:
    """Tests for PythonRunnerSkill.execute()."""

    @pytest.mark.asyncio
    async def test_simple_print(self, skill):
        result = await skill.execute(user_id=1, args=["print('hello')"])
        assert result.text == "hello"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_math_expression(self, skill):
        result = await skill.execute(user_id=1, args=["print(2", "+", "3)"])
        assert result.text == "5"

    @pytest.mark.asyncio
    async def test_no_output(self, skill):
        result = await skill.execute(user_id=1, args=["x", "=", "1"])
        assert result.text == "✅ Code executed successfully (no output)"

    @pytest.mark.asyncio
    async def test_empty_args(self, skill):
        result = await skill.execute(user_id=1, args=[])
        assert result.error is not None
        assert "Usage" in result.error

    @pytest.mark.asyncio
    async def test_blocked_import_os(self, skill):
        result = await skill.execute(user_id=1, args=["import os"])
        assert result.text is not None
        assert "blocked" in result.text.lower() or "error" in result.text.lower()

    @pytest.mark.asyncio
    async def test_blocked_import_subprocess(self, skill):
        result = await skill.execute(user_id=1, args=["import subprocess"])
        assert result.text is not None
        assert "blocked" in result.text.lower() or "error" in result.text.lower()

    @pytest.mark.asyncio
    async def test_class_attributes(self):
        assert PythonRunnerSkill.name == "python_runner"
        assert PythonRunnerSkill.command == "run"
        assert PythonRunnerSkill.permission_level == "admin"

    @pytest.mark.asyncio
    async def test_check_dependencies(self):
        assert PythonRunnerSkill.check_dependencies() is True
