"""
Unit tests for Expense-Budget Synchronization.

Tests the automatic budget deduction when expenses are created.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.account import Account
from app.models.budget import Budget, BudgetAllocation
from app.models.category import Category
from app.models.expense import Expense
from app.storage.expense_writer import (
    sync_expense_with_budget,
    create_expense_with_budget_sync,
)
from app.schemas.extraction import ExtractedExpense


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_user_with_budget(db: Session) -> tuple[User, Budget, BudgetAllocation]:
    """Create a user with an active budget and allocation."""
    # Create user
    user = User(
        id=uuid.uuid4(),
        phone_number="+573009990001",
        full_name="Budget Sync User",
        home_currency="COP",
        timezone="America/Bogota",
        onboarding_status="completed",
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create category
    category = Category(
        id=uuid.uuid4(),
        name="Food",
        slug="food",
        description="Food expenses",
        icon="🍔",
        sort_order=1,
        is_active=True,
    )
    db.add(category)
    db.flush()

    # Create budget
    budget = Budget(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Budget",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        total_amount=Decimal("5000000"),
        currency="COP",
        status="active",
    )
    db.add(budget)
    db.flush()

    # Create allocation
    allocation = BudgetAllocation(
        id=uuid.uuid4(),
        budget_id=budget.id,
        category_id=category.id,
        allocated_amount=Decimal("1500000"),
        currency="COP",
        spent_amount=Decimal("0"),
        alert_threshold_percent=80,
    )
    db.add(allocation)

    # Set current budget
    user.current_budget_id = budget.id

    db.commit()
    db.refresh(user)
    db.refresh(budget)
    db.refresh(allocation)

    return user, budget, allocation


@pytest.fixture
def test_account(db: Session, test_user_with_budget: tuple) -> Account:
    """Create a test account for the user."""
    user, _, _ = test_user_with_budget
    
    account = Account(
        id=uuid.uuid4(),
        user_id=user.id,
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
def test_expense(
    db: Session, test_user_with_budget: tuple, test_account: Account
) -> Expense:
    """Create a test expense."""
    user, budget, allocation = test_user_with_budget
    
    expense = Expense(
        id=uuid.uuid4(),
        user_id=user.id,
        account_id=test_account.id,
        category_id=allocation.category_id,
        amount_original=Decimal("50000"),
        currency_original="COP",
        description="Test expense",
        occurred_at=datetime.utcnow(),
        method="cash",
        source_type="text",
        source_meta={},
        status="pending_confirm",
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


# ─────────────────────────────────────────────────────────────────────────────
# Sync Expense with Budget Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSyncExpenseWithBudget:
    """Tests for sync_expense_with_budget function."""

    def test_sync_expense_updates_spent_amount(
        self, db: Session, test_user_with_budget: tuple, test_expense: Expense
    ):
        """Syncing expense should update allocation spent_amount."""
        user, budget, allocation = test_user_with_budget
        
        initial_spent = allocation.spent_amount
        
        result = sync_expense_with_budget(
            session=db,
            expense=test_expense,
            user=user,
        )
        
        db.refresh(allocation)
        
        assert result is not None
        assert result["budget_id"] == str(budget.id)
        assert allocation.spent_amount == initial_spent + test_expense.amount_original

    def test_sync_expense_no_budget(self, db: Session, sample_user: User, test_account: Account):
        """User without current_budget should return None."""
        # Create expense for user without budget
        expense = Expense(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            account_id=test_account.id,
            amount_original=Decimal("50000"),
            currency_original="COP",
            description="Test",
            occurred_at=datetime.utcnow(),
            method="cash",
            source_type="text",
            source_meta={},
            status="pending_confirm",
        )
        db.add(expense)
        db.commit()
        
        # Sample user doesn't have current_budget_id
        result = sync_expense_with_budget(
            session=db,
            expense=expense,
            user=sample_user,
        )
        
        assert result is None

    def test_sync_expense_with_installments(
        self, db: Session, test_user_with_budget: tuple, test_account: Account
    ):
        """Installment expense should only deduct current installment amount."""
        user, budget, allocation = test_user_with_budget
        
        # Create expense with 3 installments
        expense = Expense(
            id=uuid.uuid4(),
            user_id=user.id,
            account_id=test_account.id,
            category_id=allocation.category_id,
            amount_original=Decimal("300000"),
            currency_original="COP",
            description="Installment purchase",
            occurred_at=datetime.utcnow(),
            method="card",
            source_type="text",
            source_meta={},
            status="pending_confirm",
            installments_total=3,
            installments_paid=1,
            installment_amount=Decimal("100000"),
        )
        db.add(expense)
        db.commit()
        
        initial_spent = allocation.spent_amount
        
        result = sync_expense_with_budget(
            session=db,
            expense=expense,
            user=user,
        )
        
        db.refresh(allocation)
        
        assert result is not None
        # Should only deduct installment_amount, not full amount
        assert Decimal(result["amount_deducted"]) == Decimal("100000")
        assert allocation.spent_amount == initial_spent + Decimal("100000")

    def test_sync_expense_calculates_remaining(
        self, db: Session, test_user_with_budget: tuple, test_expense: Expense
    ):
        """Result should include correct remaining amount."""
        user, budget, allocation = test_user_with_budget
        
        result = sync_expense_with_budget(
            session=db,
            expense=test_expense,
            user=user,
        )
        
        db.refresh(allocation)
        
        expected_remaining = allocation.allocated_amount - allocation.spent_amount
        assert Decimal(result["remaining"]) == expected_remaining


# ─────────────────────────────────────────────────────────────────────────────
# Alert Threshold Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetAlertThreshold:
    """Tests for budget alert threshold detection."""

    def test_alert_triggered_at_threshold(
        self, db: Session, test_user_with_budget: tuple, test_account: Account
    ):
        """Alert should be triggered when threshold is reached."""
        user, budget, allocation = test_user_with_budget
        
        # Set spent amount to just below threshold (80% of 1,500,000 = 1,200,000)
        allocation.spent_amount = Decimal("1199000")
        db.commit()
        
        # Create expense that pushes past threshold
        expense = Expense(
            id=uuid.uuid4(),
            user_id=user.id,
            account_id=test_account.id,
            category_id=allocation.category_id,
            amount_original=Decimal("10000"),  # Will push to 1,209,000 (>80%)
            currency_original="COP",
            description="Threshold expense",
            occurred_at=datetime.utcnow(),
            method="cash",
            source_type="text",
            source_meta={},
            status="pending_confirm",
        )
        db.add(expense)
        db.commit()
        
        result = sync_expense_with_budget(
            session=db,
            expense=expense,
            user=user,
        )
        
        assert result is not None
        assert result.get("alert_triggered") is True
        assert result.get("percent_used") >= 80

