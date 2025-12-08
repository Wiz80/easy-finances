"""Unit tests for budget_writer storage module."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Budget, BudgetAllocation, Category
from app.storage.budget_writer import (
    add_allocation,
    add_funding_source,
    create_budget,
    create_budget_from_flow_data,
    get_active_budget_for_trip,
    get_budget_by_id,
    get_budget_summary,
    get_user_budgets,
    update_allocation_spent,
)


class TestCreateBudget:
    """Tests for create_budget function."""

    def test_creates_budget(self, db, sample_user):
        """Should create a budget."""
        result = create_budget(
            db=db,
            user_id=sample_user.id,
            name="Test Budget",
            total_amount=Decimal("1000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        
        assert result.success is True
        assert result.budget_id is not None
        assert result.budget.name == "Test Budget"
        assert result.budget.total_amount == Decimal("1000000")
        assert result.budget.status == "active"

    def test_creates_budget_with_allocations(self, db_with_categories, sample_user):
        """Should create budget with category allocations."""
        db = db_with_categories
        
        # Get sample user in this session
        user = db.query(sample_user.__class__).get(sample_user.id) or sample_user
        db.add(user)
        db.flush()
        
        result = create_budget(
            db=db,
            user_id=user.id,
            name="Trip Budget",
            total_amount=Decimal("5000000"),
            currency="COP",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=15),
            allocations={
                "category_food": Decimal("1500000"),
                "category_lodging": Decimal("2000000"),
            },
        )
        
        assert result.success is True
        assert len(result.budget.allocations) >= 1

    def test_creates_budget_linked_to_trip(self, db, sample_user, sample_trip):
        """Should link budget to trip."""
        result = create_budget(
            db=db,
            user_id=sample_user.id,
            name="Trip Budget",
            total_amount=Decimal("3000000"),
            currency="COP",
            start_date=sample_trip.start_date,
            end_date=sample_trip.end_date,
            trip_id=sample_trip.id,
        )
        
        assert result.success is True
        assert result.budget.trip_id == sample_trip.id


class TestCreateBudgetFromFlowData:
    """Tests for create_budget_from_flow_data function."""

    def test_creates_from_flow_data(self, db_with_categories, sample_user):
        """Should create budget from conversation flow data."""
        db = db_with_categories
        
        # Ensure user is in session
        user = db.merge(sample_user)
        
        flow_data = {
            "total_amount": "5000000",
            "category_food": "1500000",
            "category_lodging": "2000000",
            "category_transport": "800000",
        }
        
        result = create_budget_from_flow_data(
            db=db,
            user_id=user.id,
            flow_data=flow_data,
        )
        
        assert result.success is True
        assert result.budget.total_amount == Decimal("5000000")


class TestGetUserBudgets:
    """Tests for get_user_budgets function."""

    def test_returns_user_budgets(self, db_with_categories, sample_user, sample_budget):
        """Should return budgets for user."""
        db = db_with_categories
        budgets = get_user_budgets(db, sample_user.id)
        
        assert len(budgets) >= 1

    def test_filters_by_status(self, db_with_categories, sample_user, sample_budget):
        """Should filter by status."""
        db = db_with_categories
        active = get_user_budgets(db, sample_user.id, status="active")
        
        assert all(b.status == "active" for b in active)


class TestGetActiveBudgetForTrip:
    """Tests for get_active_budget_for_trip function."""

    def test_returns_active_budget(self, db_with_categories, sample_budget, sample_trip):
        """Should return active budget for trip."""
        db = db_with_categories
        budget = get_active_budget_for_trip(db, sample_trip.id)
        
        assert budget is not None
        assert budget.trip_id == sample_trip.id
        assert budget.status == "active"


class TestAddAllocation:
    """Tests for add_allocation function."""

    def test_adds_allocation(self, db_with_categories, sample_user):
        """Should add allocation to budget."""
        db = db_with_categories
        
        # Create a budget first
        budget = Budget(
            user_id=sample_user.id,
            name="Test",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            total_amount=Decimal("1000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.flush()
        
        category = db.query(Category).filter(Category.slug == "food").first()
        
        allocation = add_allocation(
            db=db,
            budget_id=budget.id,
            category_id=category.id,
            amount=Decimal("500000"),
            alert_threshold=75,
        )
        
        assert allocation is not None
        assert allocation.allocated_amount == Decimal("500000")
        assert allocation.alert_threshold_percent == 75


class TestUpdateAllocationSpent:
    """Tests for update_allocation_spent function."""

    def test_updates_spent_amount(self, db_with_categories, sample_budget):
        """Should update spent amount."""
        db = db_with_categories
        
        # Get first allocation
        allocation = sample_budget.allocations[0] if sample_budget.allocations else None
        if not allocation:
            pytest.skip("No allocations to test")
        
        initial_spent = allocation.spent_amount
        
        success = update_allocation_spent(
            db=db,
            budget_id=sample_budget.id,
            category_id=allocation.category_id,
            amount_spent=Decimal("50000"),
        )
        
        assert success is True
        
        db.refresh(allocation)
        assert allocation.spent_amount == initial_spent + Decimal("50000")


class TestAddFundingSource:
    """Tests for add_funding_source function."""

    def test_adds_cash_source(self, db, sample_user):
        """Should add cash funding source."""
        budget = Budget(
            user_id=sample_user.id,
            name="Test",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            total_amount=Decimal("1000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.flush()
        
        source = add_funding_source(
            db=db,
            budget_id=budget.id,
            source_type="cash",
            cash_currency="USD",
            cash_amount=Decimal("200"),
            is_default=False,
            priority=2,
            notes="Emergency cash",
        )
        
        assert source is not None
        assert source.source_type == "cash"
        assert source.cash_amount == Decimal("200")

    def test_adds_card_source(self, db, sample_user, sample_card):
        """Should add card funding source."""
        budget = Budget(
            user_id=sample_user.id,
            name="Test",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            total_amount=Decimal("1000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.flush()
        
        source = add_funding_source(
            db=db,
            budget_id=budget.id,
            source_type="card",
            card_id=sample_card.id,
            is_default=True,
            priority=1,
        )
        
        assert source is not None
        assert source.source_type == "card"
        assert source.card_id == sample_card.id
        assert source.is_default is True


class TestGetBudgetSummary:
    """Tests for get_budget_summary function."""

    def test_returns_summary(self, db_with_categories, sample_budget):
        """Should return budget summary dict."""
        db = db_with_categories
        summary = get_budget_summary(db, sample_budget.id)
        
        assert summary is not None
        assert summary["name"] == sample_budget.name
        assert summary["total_amount"] == float(sample_budget.total_amount)
        assert summary["currency"] == "COP"
        assert "allocations" in summary
        assert isinstance(summary["allocations"], list)

    def test_returns_none_for_invalid_id(self, db):
        """Should return None for invalid budget ID."""
        summary = get_budget_summary(db, uuid.uuid4())
        
        assert summary is None

