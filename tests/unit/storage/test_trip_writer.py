"""Unit tests for trip_writer storage module."""

import uuid
from datetime import date, timedelta

import pytest

from app.models import Trip, User
from app.storage.trip_writer import (
    cancel_trip,
    complete_trip,
    create_trip,
    get_country_info,
    get_current_trip,
    get_trip_by_id,
    get_user_trips,
    update_trip,
)


class TestGetCountryInfo:
    """Tests for get_country_info function."""

    def test_returns_info_for_known_country(self):
        """Should return currency and timezone for known country."""
        info = get_country_info("EC")
        
        assert info["country_code"] == "EC"
        assert info["currency"] == "USD"
        assert info["timezone"] == "America/Guayaquil"

    def test_returns_info_for_colombia(self):
        """Should return correct info for Colombia."""
        info = get_country_info("CO")
        
        assert info["currency"] == "COP"
        assert info["timezone"] == "America/Bogota"

    def test_returns_defaults_for_unknown_country(self):
        """Should return USD and UTC for unknown country."""
        info = get_country_info("XX")
        
        assert info["currency"] == "USD"
        assert info["timezone"] == "UTC"

    def test_handles_lowercase_input(self):
        """Should handle lowercase country codes."""
        info = get_country_info("mx")
        
        assert info["country_code"] == "MX"
        assert info["currency"] == "MXN"


class TestCreateTrip:
    """Tests for create_trip function."""

    def test_creates_trip_with_auto_currency(self, db, sample_user):
        """Should create trip with auto-detected currency."""
        result = create_trip(
            db=db,
            user_id=sample_user.id,
            name="Peru Adventure",
            start_date=date.today(),
            destination_country="PE",
        )
        
        assert result.success is True
        assert result.trip_id is not None
        assert result.trip.name == "Peru Adventure"
        assert result.trip.local_currency == "PEN"  # Auto-detected
        assert result.trip.timezone == "America/Lima"

    def test_creates_trip_with_explicit_currency(self, db, sample_user):
        """Should use explicit currency when provided."""
        result = create_trip(
            db=db,
            user_id=sample_user.id,
            name="Europe Trip",
            start_date=date.today(),
            destination_country="ES",
            local_currency="GBP",  # Override EUR
        )
        
        assert result.success is True
        assert result.trip.local_currency == "GBP"

    def test_sets_as_current_trip(self, db, sample_user):
        """Should set trip as current when set_as_current=True."""
        # Clear any existing trip
        sample_user.current_trip_id = None
        sample_user.travel_mode_active = False
        db.commit()
        
        result = create_trip(
            db=db,
            user_id=sample_user.id,
            name="New Trip",
            start_date=date.today(),
            destination_country="MX",
            set_as_current=True,
        )
        
        assert result.success is True
        
        db.refresh(sample_user)
        assert sample_user.current_trip_id == result.trip_id
        assert sample_user.travel_mode_active is True

    def test_does_not_set_current_when_disabled(self, db, sample_user):
        """Should not set as current when set_as_current=False."""
        sample_user.current_trip_id = None
        sample_user.travel_mode_active = False
        db.commit()
        
        result = create_trip(
            db=db,
            user_id=sample_user.id,
            name="Future Trip",
            start_date=date.today() + timedelta(days=30),
            destination_country="JP",
            set_as_current=False,
        )
        
        assert result.success is True
        
        db.refresh(sample_user)
        assert sample_user.current_trip_id is None


class TestGetUserTrips:
    """Tests for get_user_trips function."""

    def test_returns_user_trips(self, db, sample_user, sample_trip):
        """Should return trips for user."""
        trips = get_user_trips(db, sample_user.id)
        
        assert len(trips) >= 1
        assert any(t.id == sample_trip.id for t in trips)

    def test_filters_by_status(self, db, sample_user, sample_trip):
        """Should filter trips by status."""
        active_trips = get_user_trips(db, sample_user.id, status="active")
        
        assert all(t.status == "active" for t in active_trips)


class TestGetCurrentTrip:
    """Tests for get_current_trip function."""

    def test_returns_current_trip(self, db, sample_user, sample_trip):
        """Should return current trip for user."""
        trip = get_current_trip(db, sample_user.id)
        
        assert trip is not None
        assert trip.id == sample_trip.id

    def test_returns_none_when_no_current(self, db, sample_user):
        """Should return None when no current trip."""
        sample_user.current_trip_id = None
        db.commit()
        
        trip = get_current_trip(db, sample_user.id)
        
        assert trip is None


class TestUpdateTrip:
    """Tests for update_trip function."""

    def test_updates_trip_fields(self, db, sample_trip):
        """Should update trip fields."""
        result = update_trip(
            db=db,
            trip_id=sample_trip.id,
            name="Updated Trip Name",
            destination_city="Guayaquil",
        )
        
        assert result.success is True
        assert result.trip.name == "Updated Trip Name"
        assert result.trip.destination_city == "Guayaquil"


class TestCompleteTrip:
    """Tests for complete_trip function."""

    def test_completes_trip(self, db, sample_user, sample_trip):
        """Should mark trip as completed."""
        result = complete_trip(db, sample_trip.id)
        
        assert result.success is True
        assert result.trip.status == "completed"
        assert result.trip.is_active is False
        
        # Should deactivate travel mode
        db.refresh(sample_user)
        assert sample_user.travel_mode_active is False


class TestCancelTrip:
    """Tests for cancel_trip function."""

    def test_cancels_trip(self, db, sample_user, sample_trip):
        """Should cancel trip."""
        result = cancel_trip(db, sample_trip.id)
        
        assert result.success is True
        assert result.trip.status == "cancelled"
        assert result.trip.is_active is False

