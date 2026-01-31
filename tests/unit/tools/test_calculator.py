"""
Unit tests for Calculator Tool.

Tests:
- Basic arithmetic operations
- Complex expressions with parentheses
- Error handling (division by zero, malicious code)
- Financial helper functions
"""

from decimal import Decimal

import pytest

from app.agents.coach_agent.tools.calculator import (
    calculate,
    calculate_expression,
    CalculationResult,
    CalculatorError,
    InvalidExpressionError,
    UnsafeExpressionError,
    budget_daily,
    budget_remaining,
    budget_percentage_used,
)


# ─────────────────────────────────────────────────────────────────────────────
# Basic Arithmetic Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBasicArithmetic:
    """Tests for basic arithmetic operations."""

    def test_addition(self):
        """Test basic addition."""
        result = calculate_expression("100 + 50")
        assert result.result == Decimal("150.00")
        assert result.formatted == "150.00"

    def test_subtraction(self):
        """Test basic subtraction."""
        result = calculate_expression("500 - 150")
        assert result.result == Decimal("350.00")

    def test_multiplication(self):
        """Test basic multiplication."""
        result = calculate_expression("25 * 4")
        assert result.result == Decimal("100.00")

    def test_division(self):
        """Test basic division."""
        result = calculate_expression("100 / 4")
        assert result.result == Decimal("25.00")

    def test_modulo(self):
        """Test modulo operation."""
        result = calculate_expression("17 % 5")
        assert result.result == Decimal("2.00")

    def test_power(self):
        """Test power operation."""
        result = calculate_expression("2 ** 10")
        assert result.result == Decimal("1024.00")

    def test_negative_number(self):
        """Test negative number."""
        result = calculate_expression("-50 + 100")
        assert result.result == Decimal("50.00")


# ─────────────────────────────────────────────────────────────────────────────
# Complex Expression Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestComplexExpressions:
    """Tests for complex expressions."""

    def test_parentheses(self):
        """Test expression with parentheses."""
        result = calculate_expression("(100 + 50) * 2")
        assert result.result == Decimal("300.00")

    def test_nested_parentheses(self):
        """Test nested parentheses."""
        result = calculate_expression("((10 + 5) * 2) + 10")
        assert result.result == Decimal("40.00")

    def test_budget_daily_calculation(self):
        """Test daily budget calculation."""
        result = calculate_expression("1500000 / 30")
        assert result.result == Decimal("50000.00")
        assert result.formatted == "50,000.00"

    def test_percentage_calculation(self):
        """Test percentage calculation (IVA)."""
        result = calculate_expression("150000 * 0.16")
        assert result.result == Decimal("24000.00")

    def test_decimal_result(self):
        """Test expression with decimal result."""
        result = calculate_expression("100 / 3")
        assert result.result == Decimal("33.33")


# ─────────────────────────────────────────────────────────────────────────────
# Input Normalization Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInputNormalization:
    """Tests for input normalization."""

    def test_comma_as_decimal(self):
        """Test comma as decimal separator (European format)."""
        result = calculate_expression("100,5 + 50,5")
        assert result.result == Decimal("151.00")

    def test_unicode_operators(self):
        """Test Unicode operators."""
        result = calculate_expression("100 × 5")
        assert result.result == Decimal("500.00")

        result = calculate_expression("100 ÷ 5")
        assert result.result == Decimal("20.00")

    def test_caret_for_power(self):
        """Test caret as power operator."""
        result = calculate_expression("2^8")
        assert result.result == Decimal("256.00")

    def test_spaces_ignored(self):
        """Test that spaces are ignored."""
        result = calculate_expression("100   +   50")
        assert result.result == Decimal("150.00")


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling."""

    def test_division_by_zero(self):
        """Test division by zero raises error."""
        with pytest.raises(CalculatorError) as exc_info:
            calculate_expression("100 / 0")
        assert "cero" in str(exc_info.value).lower()

    def test_invalid_expression_syntax(self):
        """Test invalid expression raises error."""
        with pytest.raises((InvalidExpressionError, CalculatorError)):
            calculate_expression("100 ++ abc")

    def test_malicious_code_blocked(self):
        """Test that malicious code is blocked."""
        # Try to call a function
        with pytest.raises((UnsafeExpressionError, InvalidExpressionError)):
            calculate_expression("__import__('os').system('ls')")

        # Try to access attributes
        with pytest.raises((UnsafeExpressionError, InvalidExpressionError)):
            calculate_expression("().__class__")

    def test_power_too_large(self):
        """Test power exponent limit."""
        with pytest.raises(UnsafeExpressionError) as exc_info:
            calculate_expression("2 ** 1000")
        assert "large" in str(exc_info.value).lower()

    def test_result_too_large(self):
        """Test result overflow protection."""
        with pytest.raises(CalculatorError) as exc_info:
            calculate_expression("10 ** 20")
        assert "grande" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# LangChain Tool Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateTool:
    """Tests for the LangChain calculate tool."""

    def test_tool_returns_formatted_result(self):
        """Test tool returns formatted result string."""
        result = calculate.invoke("100 + 50")
        assert "150.00" in result
        assert "100 + 50" in result

    def test_tool_handles_error(self):
        """Test tool handles errors gracefully."""
        result = calculate.invoke("100 / 0")
        assert "Error" in result

    def test_tool_complex_expression(self):
        """Test tool with complex expression."""
        result = calculate.invoke("1500000 / 30")
        assert "50,000.00" in result


# ─────────────────────────────────────────────────────────────────────────────
# Financial Helper Functions Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFinancialHelpers:
    """Tests for financial helper functions."""

    def test_budget_daily(self):
        """Test daily budget calculation."""
        result = budget_daily(Decimal("1500000"), 30)
        assert result == Decimal("50000.00")

    def test_budget_daily_zero_days(self):
        """Test daily budget with zero days raises error."""
        with pytest.raises(CalculatorError):
            budget_daily(Decimal("1500000"), 0)

    def test_budget_remaining(self):
        """Test remaining budget calculation."""
        result = budget_remaining(Decimal("1000000"), Decimal("350000"))
        assert result == Decimal("650000")

    def test_budget_percentage_used(self):
        """Test percentage used calculation."""
        result = budget_percentage_used(Decimal("1000000"), Decimal("350000"))
        assert result == Decimal("35.00")

    def test_budget_percentage_used_zero_total(self):
        """Test percentage with zero total returns 0."""
        result = budget_percentage_used(Decimal("0"), Decimal("100"))
        assert result == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# CalculationResult Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculationResult:
    """Tests for CalculationResult dataclass."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = CalculationResult(
            expression="100 + 50",
            result=Decimal("150.00"),
            formatted="150.00",
        )

        d = result.to_dict()

        assert d["expression"] == "100 + 50"
        assert d["result"] == "150.00"
        assert d["formatted"] == "150.00"

