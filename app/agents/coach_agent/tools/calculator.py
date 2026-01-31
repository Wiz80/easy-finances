"""
Calculator Tool for Coach Agent.

Provides safe mathematical expression evaluation for financial calculations.
Uses AST parsing to prevent code injection attacks.

Usage:
    >>> from app.agents.coach_agent.tools.calculator import calculate
    >>> result = calculate("1500000 / 30")  # Daily budget
    >>> print(result.formatted)  # "50,000.00"
"""

import ast
import operator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Union

from langchain_core.tools import tool

from app.logging_config import get_logger

logger = get_logger(__name__)


class CalculatorError(Exception):
    """Base exception for calculator errors."""

    pass


class UnsafeExpressionError(CalculatorError):
    """Raised when expression contains unsafe operations."""

    pass


class InvalidExpressionError(CalculatorError):
    """Raised when expression cannot be parsed."""

    pass


@dataclass
class CalculationResult:
    """Result of a calculation."""

    expression: str
    result: Decimal
    formatted: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "expression": self.expression,
            "result": str(self.result),
            "formatted": self.formatted,
        }


# Allowed operators for safe evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Maximum allowed values to prevent resource exhaustion
MAX_VALUE = Decimal("1e15")  # 1 quadrillion
MAX_POWER = 100


def _eval_node(node: ast.expr) -> Union[int, float, Decimal]:
    """
    Safely evaluate an AST node.

    Only allows numeric literals and basic arithmetic operations.

    Args:
        node: AST node to evaluate

    Returns:
        Numeric result

    Raises:
        UnsafeExpressionError: If node contains unsafe operations
    """
    if isinstance(node, ast.Constant):
        # Python 3.8+ uses ast.Constant for all literals
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpressionError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.Num):
        # Python 3.7 compatibility (deprecated but might be present)
        return node.n

    elif isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        op_func = SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise UnsafeExpressionError(f"Unsupported operator: {type(node.op).__name__}")

        # Check for power operation limits
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER:
                raise UnsafeExpressionError(
                    f"Power exponent too large: {right} (max: {MAX_POWER})"
                )

        # Check for division by zero
        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            raise CalculatorError("División por cero no permitida")

        result = op_func(left, right)

        # Check for overflow
        if abs(result) > float(MAX_VALUE):
            raise CalculatorError(f"Resultado demasiado grande (max: {MAX_VALUE})")

        return result

    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op_func = SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise UnsafeExpressionError(
                f"Unsupported unary operator: {type(node.op).__name__}"
            )
        return op_func(operand)

    elif isinstance(node, ast.Expression):
        return _eval_node(node.body)

    else:
        raise UnsafeExpressionError(
            f"Unsupported expression type: {type(node).__name__}"
        )


def calculate_expression(expression: str) -> CalculationResult:
    """
    Safely evaluate a mathematical expression.

    Supports: +, -, *, /, %, ** (power)
    Supports parentheses for grouping.

    Args:
        expression: Mathematical expression string

    Returns:
        CalculationResult with result and formatted string

    Raises:
        CalculatorError: If expression is invalid or unsafe
        InvalidExpressionError: If expression cannot be parsed

    Examples:
        >>> calculate_expression("100 + 50")
        CalculationResult(expression='100 + 50', result=Decimal('150.00'), ...)

        >>> calculate_expression("1500000 / 30")
        CalculationResult(expression='1500000 / 30', result=Decimal('50000.00'), ...)

        >>> calculate_expression("(100 + 50) * 2")
        CalculationResult(expression='(100 + 50) * 2', result=Decimal('300.00'), ...)
    """
    # Clean and normalize expression
    original_expression = expression
    expr = expression.strip()

    # Replace common variants
    expr = expr.replace(",", ".")  # European decimal separator
    expr = expr.replace(" ", "")  # Remove spaces
    expr = expr.replace("×", "*")  # Unicode multiplication
    expr = expr.replace("÷", "/")  # Unicode division
    expr = expr.replace("^", "**")  # Caret for power

    logger.debug(
        "calculator_evaluate",
        original=original_expression,
        normalized=expr,
    )

    try:
        # Parse expression to AST
        tree = ast.parse(expr, mode="eval")

        # Evaluate safely
        result = _eval_node(tree)

        # Convert to Decimal and round
        result_decimal = Decimal(str(result)).quantize(Decimal("0.01"))

        # Format with thousands separator
        formatted = f"{result_decimal:,.2f}"

        logger.debug(
            "calculator_result",
            expression=original_expression,
            result=str(result_decimal),
        )

        return CalculationResult(
            expression=original_expression,
            result=result_decimal,
            formatted=formatted,
        )

    except SyntaxError as e:
        raise InvalidExpressionError(f"Expresión inválida: {expression}") from e
    except (CalculatorError, UnsafeExpressionError):
        raise
    except Exception as e:
        raise CalculatorError(f"Error calculando: {str(e)}") from e


@tool
def calculate(expression: str) -> str:
    """
    Calcula una expresión matemática.

    Útil para operaciones financieras como:
    - Calcular presupuesto diario: "1500000 / 30"
    - Sumar gastos: "50000 + 35000 + 20000"
    - Calcular porcentajes: "150000 * 0.16" (IVA)
    - Diferencias: "500000 - 350000"

    Args:
        expression: Expresión matemática a calcular.
                   Soporta: +, -, *, /, %, ** (potencia)
                   Ejemplo: "1500000 / 30"

    Returns:
        Resultado formateado como string.
        Ejemplo: "50,000.00"
    """
    try:
        result = calculate_expression(expression)
        return f"{result.expression} = {result.formatted}"
    except CalculatorError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error("calculator_unexpected_error", error=str(e), exc_info=True)
        return f"Error inesperado: {str(e)}"


# Convenience functions for direct use (not as LangChain tools)


def add(a: Decimal, b: Decimal) -> Decimal:
    """Add two decimals."""
    return a + b


def subtract(a: Decimal, b: Decimal) -> Decimal:
    """Subtract b from a."""
    return a - b


def multiply(a: Decimal, b: Decimal) -> Decimal:
    """Multiply two decimals."""
    return a * b


def divide(a: Decimal, b: Decimal) -> Decimal:
    """Divide a by b."""
    if b == 0:
        raise CalculatorError("División por cero no permitida")
    return a / b


def percentage(amount: Decimal, percent: Decimal) -> Decimal:
    """Calculate percentage of amount."""
    return amount * (percent / Decimal("100"))


def budget_daily(total: Decimal, days: int) -> Decimal:
    """Calculate daily budget from total and number of days."""
    if days <= 0:
        raise CalculatorError("El número de días debe ser mayor a 0")
    return (total / Decimal(days)).quantize(Decimal("0.01"))


def budget_remaining(total: Decimal, spent: Decimal) -> Decimal:
    """Calculate remaining budget."""
    return total - spent


def budget_percentage_used(total: Decimal, spent: Decimal) -> Decimal:
    """Calculate percentage of budget used."""
    if total == 0:
        return Decimal("0")
    return ((spent / total) * Decimal("100")).quantize(Decimal("0.01"))

