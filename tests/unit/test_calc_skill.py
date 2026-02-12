"""Unit tests for CalculatorSkill."""

import math

import pytest

from src.skills.calc import CalculatorSkill, safe_eval


@pytest.fixture
def skill():
    return CalculatorSkill(config={"enabled": True})


class TestSafeEval:
    """Tests for the safe_eval function."""

    def test_basic_addition(self):
        assert safe_eval("2 + 3") == 5

    def test_basic_subtraction(self):
        assert safe_eval("10 - 4") == 6

    def test_multiplication(self):
        assert safe_eval("6 * 7") == 42

    def test_division(self):
        assert safe_eval("10 / 4") == 2.5

    def test_floor_division(self):
        assert safe_eval("10 // 3") == 3

    def test_modulo(self):
        assert safe_eval("10 % 3") == 1

    def test_power(self):
        assert safe_eval("2 ** 10") == 1024

    def test_unary_minus(self):
        assert safe_eval("-5") == -5

    def test_unary_plus(self):
        assert safe_eval("+5") == 5

    def test_nested_expression(self):
        assert safe_eval("(2 + 3) * 4") == 20

    def test_pi_constant(self):
        assert safe_eval("pi") == math.pi

    def test_e_constant(self):
        assert safe_eval("e") == math.e

    def test_sin_function(self):
        result = safe_eval("sin(0)")
        assert result == pytest.approx(0.0)

    def test_cos_function(self):
        result = safe_eval("cos(0)")
        assert result == pytest.approx(1.0)

    def test_sqrt_function(self):
        assert safe_eval("sqrt(16)") == 4.0

    def test_abs_function(self):
        assert safe_eval("abs(-42)") == 42

    def test_log_function(self):
        assert safe_eval("log(1)") == pytest.approx(0.0)

    def test_log10_function(self):
        assert safe_eval("log10(100)") == pytest.approx(2.0)

    def test_round_function(self):
        assert safe_eval("round(3.7)") == 4

    def test_pow_function(self):
        assert safe_eval("pow(2, 8)") == 256

    def test_combined_expression(self):
        result = safe_eval("2 + 3 * sin(pi / 2)")
        assert result == pytest.approx(5.0)

    def test_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            safe_eval("1 / 0")

    def test_floor_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            safe_eval("1 // 0")

    def test_syntax_error(self):
        with pytest.raises(SyntaxError):
            safe_eval("2 +")

    def test_disallowed_name(self):
        with pytest.raises(ValueError, match="Name not allowed"):
            safe_eval("x + 1")

    def test_disallowed_function(self):
        with pytest.raises(ValueError, match="Function not allowed"):
            safe_eval("exit()")

    def test_import_blocked(self):
        with pytest.raises(ValueError, match="Function not allowed"):
            safe_eval("__import__('os')")

    def test_attribute_access_blocked(self):
        with pytest.raises(ValueError):
            safe_eval("math.pi")


class TestCalculatorSkillExecute:
    """Tests for CalculatorSkill.execute()."""

    @pytest.mark.asyncio
    async def test_successful_calculation(self, skill):
        result = await skill.execute(user_id=1, args=["2", "+", "3"])
        assert result.text == "🧮 Result: 5"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_float_result(self, skill):
        result = await skill.execute(user_id=1, args=["10", "/", "3"])
        assert result.text is not None
        assert "🧮 Result:" in result.text

    @pytest.mark.asyncio
    async def test_empty_expression(self, skill):
        result = await skill.execute(user_id=1, args=[])
        assert result.error is not None
        assert "Usage" in result.error

    @pytest.mark.asyncio
    async def test_division_by_zero_error(self, skill):
        result = await skill.execute(user_id=1, args=["1", "/", "0"])
        assert result.error == "Division by zero"

    @pytest.mark.asyncio
    async def test_syntax_error(self, skill):
        result = await skill.execute(user_id=1, args=["2", "+"])
        assert result.error == "Invalid expression syntax"

    @pytest.mark.asyncio
    async def test_disallowed_construct(self, skill):
        result = await skill.execute(user_id=1, args=["exit()"])
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_class_attributes(self):
        assert CalculatorSkill.name == "calculator"
        assert CalculatorSkill.command == "calc"
        assert CalculatorSkill.permission_level == "guest"

    @pytest.mark.asyncio
    async def test_check_dependencies(self):
        assert CalculatorSkill.check_dependencies() is True
