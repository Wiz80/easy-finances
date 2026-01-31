"""
Unit tests for Expense model.

Tests the new installment fields added in Phase 1:
- installments_total
- installments_paid
- installment_amount
- total_debt_amount
"""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.account import Account
from app.models.category import Category
from app.models.expense import Expense


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user for expense tests."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573008887777",
        full_name="Expense Test User",
        home_currency="COP",
        timezone="America/Bogota",
        onboarding_status="completed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_account(db: Session, test_user: User) -> Account:
    """Create a test account for expense tests."""
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Account",
        account_type="checking",
        currency="COP",
        is_active=True,
        is_default=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def test_category(db: Session) -> Category:
    """Create a test category for expense tests."""
    category = Category(
        id=uuid.uuid4(),
        name="Test Category",
        slug="test_category",
        description="Test category",
        icon="🧪",
        sort_order=99,
        is_active=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# ─────────────────────────────────────────────────────────────────────────────
# Basic Expense Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseModel:
    """Tests for Expense model basic functionality."""

    def test_create_expense(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """Expense should be created with required fields."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Almuerzo",
            occurred_at=datetime.utcnow(),
            method="cash",
            source_type="text",
            source_meta={"msg_id": "test123"},
            status="pending_confirm",
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        assert expense.id is not None
        assert expense.amount_original == Decimal("50000")
        assert expense.description == "Almuerzo"

    def test_expense_default_installments(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """Expense should have default installment values."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("100000"),
            currency_original="COP",
            description="Compra normal",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            status="pending_confirm",
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        # Default values
        assert expense.installments_total == 1
        assert expense.installments_paid == 1
        assert expense.installment_amount is None
        assert expense.total_debt_amount is None


# ─────────────────────────────────────────────────────────────────────────────
# Installment Fields Tests (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseInstallmentFields:
    """Tests for the new installment fields."""

    def test_expense_with_installments(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """Expense should accept installment fields."""
        total_amount = Decimal("300000")
        installments = 3
        installment_amount = total_amount / installments

        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=total_amount,
            currency_original="COP",
            description="Compra a cuotas",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            status="pending_confirm",
            installments_total=installments,
            installments_paid=1,
            installment_amount=installment_amount,
            total_debt_amount=total_amount,
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        assert expense.installments_total == 3
        assert expense.installments_paid == 1
        assert expense.installment_amount == Decimal("100000")
        assert expense.total_debt_amount == Decimal("300000")

    def test_expense_six_installments(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """Expense should work with 6 installments."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Electrodoméstico",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            status="pending_confirm",
            installments_total=6,
            installments_paid=2,
            installment_amount=Decimal("100000"),
            total_debt_amount=Decimal("600000"),
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        assert expense.installments_total == 6
        assert expense.installments_paid == 2


# ─────────────────────────────────────────────────────────────────────────────
# Installment Properties Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseInstallmentProperties:
    """Tests for the installment-related properties."""

    def test_is_installment_purchase_true(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """is_installment_purchase should be True for multi-installment expenses."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("300000"),
            currency_original="COP",
            description="Compra a cuotas",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=3,
            installments_paid=1,
            installment_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()

        assert expense.is_installment_purchase is True

    def test_is_installment_purchase_false(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """is_installment_purchase should be False for single payment expenses."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Pago único",
            occurred_at=datetime.utcnow(),
            method="cash",
            source_type="text",
            source_meta={},
            installments_total=1,
            installments_paid=1,
        )
        db.add(expense)
        db.commit()

        assert expense.is_installment_purchase is False

    def test_installments_remaining(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """installments_remaining should calculate correctly."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Compra grande",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=6,
            installments_paid=2,
            installment_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()

        assert expense.installments_remaining == 4  # 6 - 2 = 4

    def test_installments_remaining_zero(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """installments_remaining should be 0 when all paid."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("300000"),
            currency_original="COP",
            description="Compra pagada",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=3,
            installments_paid=3,
            installment_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()

        assert expense.installments_remaining == 0

    def test_remaining_debt_calculation(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """remaining_debt should calculate debt correctly."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("600000"),
            currency_original="COP",
            description="Compra",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=6,
            installments_paid=2,
            installment_amount=Decimal("100000"),
            total_debt_amount=Decimal("600000"),
        )
        db.add(expense)
        db.commit()

        # Remaining = (6 - 2) * 100000 = 400000
        assert expense.remaining_debt == Decimal("400000")

    def test_remaining_debt_zero_for_single_payment(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """remaining_debt should be 0 for single payment expenses."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Pago único",
            occurred_at=datetime.utcnow(),
            method="cash",
            source_type="text",
            source_meta={},
            installments_total=1,
            installments_paid=1,
        )
        db.add(expense)
        db.commit()

        assert expense.remaining_debt == Decimal("0")

    def test_remaining_debt_with_none_installment_amount(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """remaining_debt should handle None installment_amount."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("300000"),
            currency_original="COP",
            description="Compra",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=3,
            installments_paid=1,
            installment_amount=None,  # Not set
        )
        db.add(expense)
        db.commit()

        # Should return 0 if installment_amount is None
        assert expense.remaining_debt == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseInstallmentEdgeCases:
    """Edge case tests for installment functionality."""

    def test_installments_paid_exceeds_total(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """installments_remaining should not be negative."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("300000"),
            currency_original="COP",
            description="Error case",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=3,
            installments_paid=5,  # More than total (edge case)
            installment_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()

        # Should return 0, not negative
        assert expense.installments_remaining == 0

    def test_expense_with_decimal_installment_amount(
        self, db: Session, test_user: User, test_account: Account, test_category: Category
    ):
        """Installment amount should support decimal values."""
        expense = Expense(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            category_id=test_category.id,
            amount_original=Decimal("100000"),
            currency_original="COP",
            description="Compra con decimales",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            installments_total=3,
            installments_paid=1,
            installment_amount=Decimal("33333.33"),
            total_debt_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        assert expense.installment_amount == Decimal("33333.33")
        # Remaining debt: 2 * 33333.33 = 66666.66
        assert expense.remaining_debt == Decimal("66666.66")

