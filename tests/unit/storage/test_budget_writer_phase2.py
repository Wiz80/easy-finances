"""
Unit tests for Budget Writer - Phase 2 additions.

Tests the create_budget_and_set_current function.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.budget import Budget, BudgetAllocation
from app.models.category import Category
from app.storage.budget_writer import (
    create_budget_and_set_current,
    get_unexpected_category,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_without_budget(db: Session) -> User:
    """Create a user without any budget."""
    user = User(
        id=uuid.uuid4(),
        phone_number="+573001234599",
        full_name="No Budget User",
        nickname="NoBudget",
        home_currency="COP",
        country="CO",
        timezone="America/Bogota",
        preferred_language="es",
        onboarding_status="completed",
        onboarding_completed_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def unexpected_category(db: Session) -> Category:
    """Create the unexpected expenses category."""
    category = Category(
        id=uuid.uuid4(),
        name="Gastos Inesperados",
        slug="unexpected_expenses",
        description="Unexpected expenses",
        icon="🚨",
        sort_order=99,
        is_active=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def misc_category(db: Session) -> Category:
    """Create the misc category as fallback."""
    category = Category(
        id=uuid.uuid4(),
        name="Otros",
        slug="misc",
        description="Other expenses",
        icon="📦",
        sort_order=100,
        is_active=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# ─────────────────────────────────────────────────────────────────────────────
# Create Budget and Set Current Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateBudgetAndSetCurrent:
    """Tests for create_budget_and_set_current function."""

    def test_creates_budget(
        self, db: Session, user_without_budget: User, unexpected_category: Category
    ):
        """Should create a new budget."""
        budget = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Test Budget",
            amount=Decimal("5000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        assert budget is not None
        assert budget.name == "Test Budget"
        assert budget.total_amount == Decimal("5000000")
        assert budget.currency == "COP"
        assert budget.status == "active"

    def test_sets_current_budget(
        self, db: Session, user_without_budget: User, unexpected_category: Category
    ):
        """Should set the budget as user's current_budget."""
        budget = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Current Budget",
            amount=Decimal("3000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        db.refresh(user_without_budget)

        assert user_without_budget.current_budget_id == budget.id

    def test_creates_default_allocation(
        self, db: Session, user_without_budget: User, unexpected_category: Category
    ):
        """Should create allocation for unexpected expenses."""
        budget = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Budget With Allocation",
            amount=Decimal("2000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        # Check allocation exists
        allocation = db.query(BudgetAllocation).filter(
            BudgetAllocation.budget_id == budget.id
        ).first()

        assert allocation is not None
        assert allocation.category_id == unexpected_category.id
        assert allocation.allocated_amount == Decimal("2000000")
        assert allocation.spent_amount == Decimal("0")

    def test_uses_misc_category_fallback(
        self, db: Session, user_without_budget: User, misc_category: Category
    ):
        """Should use misc category if unexpected_expenses doesn't exist."""
        budget = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Fallback Budget",
            amount=Decimal("1500000"),
            currency="USD",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        allocation = db.query(BudgetAllocation).filter(
            BudgetAllocation.budget_id == budget.id
        ).first()

        assert allocation is not None
        assert allocation.category_id == misc_category.id

    def test_can_link_to_trip(
        self, db: Session, user_without_budget: User, unexpected_category: Category
    ):
        """Should link budget to trip if provided."""
        trip_id = uuid.uuid4()

        budget = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Trip Budget",
            amount=Decimal("8000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            trip_id=trip_id,
        )

        assert budget.trip_id == trip_id


# ─────────────────────────────────────────────────────────────────────────────
# Get Unexpected Category Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetUnexpectedCategory:
    """Tests for get_unexpected_category function."""

    def test_returns_unexpected_category(
        self, db: Session, unexpected_category: Category
    ):
        """Should return unexpected_expenses category."""
        category = get_unexpected_category(db)
        
        assert category is not None
        assert category.slug == "unexpected_expenses"

    def test_returns_misc_as_fallback(self, db: Session, misc_category: Category):
        """Should return misc if unexpected_expenses doesn't exist."""
        category = get_unexpected_category(db)
        
        assert category is not None
        assert category.slug == "misc"

    def test_returns_none_if_no_fallback(self, db: Session):
        """Should return None if no suitable category exists."""
        # No categories in DB
        category = get_unexpected_category(db)
        
        assert category is None


# ─────────────────────────────────────────────────────────────────────────────
# Multiple Budgets Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleBudgets:
    """Tests for handling multiple budgets."""

    def test_new_budget_replaces_current(
        self, db: Session, user_without_budget: User, unexpected_category: Category
    ):
        """Creating a new budget should replace current_budget."""
        # Create first budget
        budget1 = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="First Budget",
            amount=Decimal("1000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=15),
        )

        db.refresh(user_without_budget)
        assert user_without_budget.current_budget_id == budget1.id

        # Create second budget
        budget2 = create_budget_and_set_current(
            db=db,
            user=user_without_budget,
            name="Second Budget",
            amount=Decimal("2000000"),
            currency="COP",
            start_date=date.today() + timedelta(days=16),
            end_date=date.today() + timedelta(days=45),
        )

        db.refresh(user_without_budget)
        assert user_without_budget.current_budget_id == budget2.id

        # First budget still exists
        db.refresh(budget1)
        assert budget1.status == "active"

