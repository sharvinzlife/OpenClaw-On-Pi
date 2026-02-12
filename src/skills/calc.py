"""Calculator skill — safe math expression evaluator using AST parsing."""

import ast
import math
from typing import Union

from src.skills.base_skill import BaseSkill, SkillResult

# Whitelisted functions from math module
SAFE_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "pow": pow,
}

# Whitelisted constants
SAFE_NAMES = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate a whitelisted AST node.

    Args:
        node: An AST node from a parsed expression.

    Returns:
        The numeric result of evaluating the node.

    Raises:
        ValueError: If the node type is not whitelisted.
    """
    # Python 3.8+ uses ast.Constant; older used ast.Num
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.Pow):
            return left**right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        raise ValueError(f"Unsupported binary operator: {type(op).__name__}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named function calls are allowed")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Function not allowed: {func_name}")
        args = [_eval_node(arg) for arg in node.args]
        return SAFE_FUNCTIONS[func_name](*args)

    if isinstance(node, ast.Name):
        if node.id in SAFE_NAMES:
            return SAFE_NAMES[node.id]
        raise ValueError(f"Name not allowed: {node.id}")

    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def safe_eval(expression: str) -> Union[int, float]:
    """Safely evaluate a math expression using AST parsing.

    Args:
        expression: A math expression string (e.g. "2 + 3 * sin(pi/2)").

    Returns:
        The numeric result.

    Raises:
        SyntaxError: If the expression cannot be parsed.
        ValueError: If the expression contains disallowed constructs.
        ZeroDivisionError: If division by zero occurs.
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body)


class CalculatorSkill(BaseSkill):
    """Evaluate math expressions safely using AST-based parsing."""

    name = "calculator"
    command = "calc"
    description = "Evaluate math expressions"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        """Evaluate the given math expression.

        Args:
            user_id: Telegram user ID.
            args: Command arguments — joined into a single expression string.

        Returns:
            SkillResult with the formatted result or an error message.
        """
        expression = " ".join(args).strip()
        if not expression:
            return SkillResult(error="Usage: /calc <expression>\nExample: /calc 2 + 3 * sin(pi/2)")

        try:
            result = safe_eval(expression)
            # Format: drop trailing .0 for clean integer results
            if isinstance(result, float) and result == int(result) and not math.isinf(result):
                formatted = str(int(result))
            else:
                formatted = str(result)
            return SkillResult(text=f"🧮 Result: {formatted}")
        except SyntaxError:
            return SkillResult(error="Invalid expression syntax")
        except ZeroDivisionError:
            return SkillResult(error="Division by zero")
        except ValueError as e:
            return SkillResult(error=str(e))

    @classmethod
    def check_dependencies(cls) -> bool:
        """No external dependencies needed."""
        return True
