"""
Unit tests for User model.

Tests the new fields added in Phase 1:
- current_budget_id
- country
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.budget import Budget


# ─────────────────────────────────────────────────────────────────────────────
# User Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestUserModel:
    """Tests for User model basic fields."""

    def test_create_user(self, db: Session):
        """User should be created with required fields."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009998888",
            full_name="Test User",
            home_currency="COP",
            timezone="America/Bogota",
            preferred_language="es",
            onboarding_status="pending",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.phone_number == "+573009998888"
        assert user.full_name == "Test User"

    def test_user_display_name_with_nickname(self, db: Session):
        """Display name should return nickname if set."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009997777",
            full_name="Juan Carlos Rodríguez",
            nickname="Juanca",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()

        assert user.display_name == "Juanca"

    def test_user_display_name_without_nickname(self, db: Session):
        """Display name should return full_name if no nickname."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009996666",
            full_name="María López",
            nickname=None,
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()

        assert user.display_name == "María López"

    def test_user_needs_onboarding_pending(self, db: Session):
        """User with pending status should need onboarding."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009995555",
            full_name="Usuario",
            home_currency="USD",
            timezone="America/Mexico_City",
            onboarding_status="pending",
            is_active=True,
        )
        db.add(user)
        db.commit()

        assert user.needs_onboarding is True
        assert user.is_onboarding_complete is False

    def test_user_needs_onboarding_in_progress(self, db: Session):
        """User with in_progress status should need onboarding."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009994444",
            full_name="Usuario",
            home_currency="USD",
            timezone="America/Mexico_City",
            onboarding_status="in_progress",
            onboarding_step="currency",
            is_active=True,
        )
        db.add(user)
        db.commit()

        assert user.needs_onboarding is True

    def test_user_onboarding_complete(self, db: Session):
        """User with completed status should not need onboarding."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009993333",
            full_name="Harrison",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            onboarding_completed_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(user)
        db.commit()

        assert user.needs_onboarding is False
        assert user.is_onboarding_complete is True


# ─────────────────────────────────────────────────────────────────────────────
# New Fields Tests (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

class TestUserCountryField:
    """Tests for the new country field."""

    def test_user_with_country(self, db: Session):
        """User should accept country code."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009992222",
            full_name="Test User",
            home_currency="COP",
            country="CO",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.country == "CO"

    def test_user_country_nullable(self, db: Session):
        """Country field should be nullable."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009991111",
            full_name="Test User",
            home_currency="COP",
            country=None,
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.country is None


class TestUserCurrentBudgetRelationship:
    """Tests for the current_budget_id relationship."""

    def test_user_without_current_budget(self, db: Session):
        """User without current_budget_id should have None."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009880000",
            full_name="Test User",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.current_budget_id is None
        assert user.current_budget is None

    def test_user_with_current_budget(self, db: Session):
        """User should be able to have a current_budget."""
        # Create user first
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009881111",
            full_name="Test User",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create budget
        budget = Budget(
            id=uuid.uuid4(),
            user_id=user.id,
            name="January Budget",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            total_amount=Decimal("5000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)

        # Assign current budget
        user.current_budget_id = budget.id
        db.commit()
        db.refresh(user)

        assert user.current_budget_id == budget.id
        assert user.current_budget is not None
        assert user.current_budget.name == "January Budget"

    def test_user_current_budget_independent_of_trip(self, db: Session):
        """Current budget should work without a trip."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009882222",
            full_name="Test User",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            travel_mode_active=False,
            current_trip_id=None,
            is_active=True,
        )
        db.add(user)
        db.commit()

        # Create budget without trip
        budget = Budget(
            id=uuid.uuid4(),
            user_id=user.id,
            trip_id=None,  # No trip
            name="Monthly Budget",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            total_amount=Decimal("3000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.commit()

        user.current_budget_id = budget.id
        db.commit()
        db.refresh(user)

        assert user.current_budget_id is not None
        assert user.current_trip_id is None
        assert user.travel_mode_active is False
        assert user.current_budget.trip_id is None

    def test_user_budget_deletion_sets_null(self, db: Session):
        """Deleting budget should set current_budget_id to NULL."""
        user = User(
            id=uuid.uuid4(),
            phone_number="+573009883333",
            full_name="Test User",
            home_currency="COP",
            timezone="America/Bogota",
            onboarding_status="completed",
            is_active=True,
        )
        db.add(user)
        db.commit()

        budget = Budget(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Temp Budget",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            total_amount=Decimal("1000000"),
            currency="COP",
            status="active",
        )
        db.add(budget)
        db.commit()

        user.current_budget_id = budget.id
        db.commit()

        # Delete budget
        db.delete(budget)
        db.commit()
        db.refresh(user)

        # current_budget_id should be NULL due to ON DELETE SET NULL
        assert user.current_budget_id is None

