"""Unit tests for user_writer storage module."""

import uuid
from datetime import datetime

import pytest

from app.models import User
from app.storage.user_writer import (
    activate_travel_mode,
    complete_onboarding,
    create_user,
    deactivate_travel_mode,
    get_user_by_id,
    get_user_by_phone,
    set_onboarding_step,
    update_user,
)


class TestGetUserByPhone:
    """Tests for get_user_by_phone function."""

    def test_returns_user_when_found(self, db, sample_user):
        """Should return user when phone number exists."""
        result = get_user_by_phone(db, sample_user.phone_number)
        
        assert result is not None
        assert result.id == sample_user.id
        assert result.phone_number == sample_user.phone_number

    def test_returns_none_when_not_found(self, db):
        """Should return None when phone number doesn't exist."""
        result = get_user_by_phone(db, "+1234567890")
        
        assert result is None


class TestGetUserById:
    """Tests for get_user_by_id function."""

    def test_returns_user_when_found(self, db, sample_user):
        """Should return user when ID exists."""
        result = get_user_by_id(db, sample_user.id)
        
        assert result is not None
        assert result.id == sample_user.id

    def test_returns_none_when_not_found(self, db):
        """Should return None when ID doesn't exist."""
        result = get_user_by_id(db, uuid.uuid4())
        
        assert result is None


class TestCreateUser:
    """Tests for create_user function."""

    def test_creates_new_user(self, db):
        """Should create a new user with given data."""
        result = create_user(
            db=db,
            phone_number="+573009999999",
            full_name="New User",
            nickname="New",
            home_currency="COP",
            timezone="America/Bogota",
        )
        
        assert result.success is True
        assert result.is_new is True
        assert result.user_id is not None
        
        # Verify in database
        user = get_user_by_id(db, result.user_id)
        assert user.full_name == "New User"
        assert user.home_currency == "COP"
        assert user.onboarding_status == "pending"

    def test_returns_existing_user(self, db, sample_user):
        """Should return existing user when phone already exists."""
        result = create_user(
            db=db,
            phone_number=sample_user.phone_number,
            full_name="Different Name",
        )
        
        assert result.success is True
        assert result.is_new is False
        assert result.user_id == sample_user.id


class TestUpdateUser:
    """Tests for update_user function."""

    def test_updates_user_fields(self, db, sample_user):
        """Should update allowed fields."""
        result = update_user(
            db=db,
            user_id=sample_user.id,
            full_name="Updated Name",
            home_currency="USD",
        )
        
        assert result.success is True
        
        # Verify changes
        user = get_user_by_id(db, sample_user.id)
        assert user.full_name == "Updated Name"
        assert user.home_currency == "USD"

    def test_fails_for_nonexistent_user(self, db):
        """Should fail when user doesn't exist."""
        result = update_user(
            db=db,
            user_id=uuid.uuid4(),
            full_name="New Name",
        )
        
        assert result.success is False
        assert "not found" in result.error.lower()


class TestCompleteOnboarding:
    """Tests for complete_onboarding function."""

    def test_completes_onboarding(self, db, new_user):
        """Should mark onboarding as complete."""
        result = complete_onboarding(
            db=db,
            user_id=new_user.id,
            full_name="Harrison",
            home_currency="COP",
            timezone="America/Bogota",
        )
        
        assert result.success is True
        
        # Verify changes
        user = get_user_by_id(db, new_user.id)
        assert user.onboarding_status == "completed"
        assert user.onboarding_completed_at is not None
        assert user.full_name == "Harrison"


class TestSetOnboardingStep:
    """Tests for set_onboarding_step function."""

    def test_sets_step(self, db, new_user):
        """Should set onboarding step."""
        result = set_onboarding_step(db, new_user.id, "currency")
        
        assert result.success is True
        
        user = get_user_by_id(db, new_user.id)
        assert user.onboarding_status == "in_progress"
        assert user.onboarding_step == "currency"


class TestTravelMode:
    """Tests for travel mode functions."""

    def test_activate_travel_mode(self, db, sample_user, sample_trip):
        """Should activate travel mode with trip."""
        # First deactivate
        sample_user.travel_mode_active = False
        sample_user.current_trip_id = None
        db.commit()
        
        result = activate_travel_mode(db, sample_user.id, sample_trip.id)
        
        assert result.success is True
        
        user = get_user_by_id(db, sample_user.id)
        assert user.travel_mode_active is True
        assert user.current_trip_id == sample_trip.id

    def test_deactivate_travel_mode(self, db, sample_user, sample_trip):
        """Should deactivate travel mode."""
        result = deactivate_travel_mode(db, sample_user.id)
        
        assert result.success is True
        
        user = get_user_by_id(db, sample_user.id)
        assert user.travel_mode_active is False
        assert user.current_trip_id is None

