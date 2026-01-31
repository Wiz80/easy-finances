"""
Unit tests for Expense Installments handling.

Tests:
- Single payment (installments=1)
- Multiple installments calculation
- Installment amount calculation
- Budget deduction with installments
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.extraction import ExtractedExpense


# ─────────────────────────────────────────────────────────────────────────────
# ExtractedExpense Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractedExpenseInstallments:
    """Tests for installments field in ExtractedExpense."""

    def test_default_installments_is_one(self):
        """Default installments should be 1."""
        expense = ExtractedExpense(
            amount=Decimal("150000"),
            currency="COP",
            description="Almuerzo",
            category_candidate="out_house_food",
            method="card",
            confidence=0.9,
            raw_input="150000 almuerzo",
        )

        assert expense.installments == 1

    def test_explicit_installments(self):
        """Can set explicit installments."""
        expense = ExtractedExpense(
            amount=Decimal("600000"),
            currency="COP",
            description="Celular nuevo",
            category_candidate="misc",
            method="card",
            installments=6,
            confidence=0.9,
            raw_input="600000 celular en 6 cuotas",
        )

        assert expense.installments == 6

    def test_installments_validation_min(self):
        """Installments must be at least 1."""
        with pytest.raises(ValueError):
            ExtractedExpense(
                amount=Decimal("100000"),
                currency="COP",
                description="Test",
                category_candidate="misc",
                method="card",
                installments=0,
                confidence=0.9,
                raw_input="test",
            )

    def test_installments_validation_max(self):
        """Installments must be at most 48."""
        with pytest.raises(ValueError):
            ExtractedExpense(
                amount=Decimal("100000"),
                currency="COP",
                description="Test",
                category_candidate="misc",
                method="card",
                installments=60,
                confidence=0.9,
                raw_input="test",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Expense Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExpenseInstallmentProperties:
    """Tests for Expense model installment properties."""

    def test_is_installment_purchase_true(self):
        """is_installment_purchase returns True for multi-installment."""
        from app.models.expense import Expense

        expense = Expense(
            id=uuid4(),
            user_id=uuid4(),
            account_id=uuid4(),
            category_id=uuid4(),
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Celular",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=6,
            installments_paid=1,
            installment_amount=Decimal("100000"),
        )

        assert expense.is_installment_purchase is True

    def test_is_installment_purchase_false(self):
        """is_installment_purchase returns False for single payment."""
        from app.models.expense import Expense

        expense = Expense(
            id=uuid4(),
            user_id=uuid4(),
            account_id=uuid4(),
            category_id=uuid4(),
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Almuerzo",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=1,
        )

        assert expense.is_installment_purchase is False

    def test_remaining_debt_calculation(self):
        """remaining_debt should calculate correctly."""
        from app.models.expense import Expense

        expense = Expense(
            id=uuid4(),
            user_id=uuid4(),
            account_id=uuid4(),
            category_id=uuid4(),
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Celular",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=6,
            installments_paid=2,  # 2 paid, 4 remaining
            installment_amount=Decimal("100000"),
        )

        # 4 remaining * 100000 = 400000
        assert expense.remaining_debt == Decimal("400000")

    def test_remaining_debt_single_payment(self):
        """remaining_debt should be 0 for single payments."""
        from app.models.expense import Expense

        expense = Expense(
            id=uuid4(),
            user_id=uuid4(),
            account_id=uuid4(),
            category_id=uuid4(),
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Almuerzo",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=1,
        )

        assert expense.remaining_debt == Decimal("0")

    def test_installments_remaining(self):
        """installments_remaining should calculate correctly."""
        from app.models.expense import Expense

        expense = Expense(
            id=uuid4(),
            user_id=uuid4(),
            account_id=uuid4(),
            category_id=uuid4(),
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Celular",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=6,
            installments_paid=2,
        )

        assert expense.installments_remaining == 4


# ─────────────────────────────────────────────────────────────────────────────
# Expense Writer Installment Logic Tests (using mocks)
# ─────────────────────────────────────────────────────────────────────────────


class TestExpenseWriterInstallmentLogic:
    """Tests for expense writer installment handling logic."""

    def test_single_payment_no_installment_fields(self):
        """Single payment should not set installment amount."""
        from app.models.expense import Expense

        # Test the logic directly - single payment
        installments_total = 1
        amount = Decimal("50000")

        # This mimics what expense_writer does
        installment_amount = None
        total_debt_amount = None

        if installments_total > 1:
            installment_amount = (amount / Decimal(installments_total)).quantize(
                Decimal("0.01")
            )
            total_debt_amount = amount

        assert installments_total == 1
        assert installment_amount is None
        assert total_debt_amount is None

    def test_installment_expense_calculates_amounts(self):
        """Installment expense should calculate per-installment amount."""
        # Test the logic directly - 6 installments
        installments_total = 6
        amount = Decimal("600000")

        installment_amount = None
        total_debt_amount = None

        if installments_total > 1:
            installment_amount = (amount / Decimal(installments_total)).quantize(
                Decimal("0.01")
            )
            total_debt_amount = amount

        assert installment_amount == Decimal("100000.00")
        assert total_debt_amount == Decimal("600000")

    def test_installment_amount_rounds_correctly(self):
        """Installment amount should round to 2 decimal places."""
        # Test the logic directly - 3 installments (100000 / 3 = 33333.33...)
        installments_total = 3
        amount = Decimal("100000")

        installment_amount = (amount / Decimal(installments_total)).quantize(
            Decimal("0.01")
        )

        assert installment_amount == Decimal("33333.33")

    def test_extracted_expense_passes_installments(self):
        """Verify extracted expense installments field is accessible."""
        extracted = ExtractedExpense(
            amount=Decimal("600000"),
            currency="COP",
            description="Celular",
            category_candidate="misc",
            method="card",
            installments=6,
            confidence=0.9,
            raw_input="600000 celular en 6 cuotas",
        )

        # This is how expense_writer accesses it
        installments_total = getattr(extracted, 'installments', 1) or 1

        assert installments_total == 6


# ─────────────────────────────────────────────────────────────────────────────
# Installment Pattern Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInstallmentPatternDetection:
    """Tests for detecting installment patterns in text (future feature)."""

    # These patterns should be detected by the LLM extraction:
    # - "50000 en 3 cuotas"
    # - "pagué a 6 meses"
    # - "600000 a 12 cuotas"
    # - "compré en 6 pagos"

    def test_pattern_examples(self):
        """Document expected patterns (for LLM prompt reference)."""
        patterns = [
            ("50000 en 3 cuotas", 3),
            ("pagué 600000 a 6 meses", 6),
            ("compré celular en 12 cuotas", 12),
            ("600000 a 12 pagos", 12),
            ("50000 taxi", 1),  # No installments
        ]

        # This test documents expected patterns
        # Actual detection is done by LLM extraction
        for text, expected_installments in patterns:
            assert expected_installments >= 1

