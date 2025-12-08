"""
Trip storage operations for the Configuration Agent.

Handles trip creation, updates, and status management.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Account, Trip, User

logger = get_logger(__name__)


# Country to currency mapping for common destinations
COUNTRY_CURRENCIES = {
    "EC": "USD",  # Ecuador
    "US": "USD",  # United States
    "MX": "MXN",  # Mexico
    "CO": "COP",  # Colombia
    "PE": "PEN",  # Peru
    "CL": "CLP",  # Chile
    "AR": "ARS",  # Argentina
    "BR": "BRL",  # Brazil
    "ES": "EUR",  # Spain
    "FR": "EUR",  # France
    "DE": "EUR",  # Germany
    "IT": "EUR",  # Italy
    "GB": "GBP",  # United Kingdom
    "CA": "CAD",  # Canada
    "JP": "JPY",  # Japan
}

# Country to timezone mapping for common destinations
COUNTRY_TIMEZONES = {
    "EC": "America/Guayaquil",
    "US": "America/New_York",
    "MX": "America/Mexico_City",
    "CO": "America/Bogota",
    "PE": "America/Lima",
    "CL": "America/Santiago",
    "AR": "America/Buenos_Aires",
    "BR": "America/Sao_Paulo",
    "ES": "Europe/Madrid",
    "FR": "Europe/Paris",
    "DE": "Europe/Berlin",
    "IT": "Europe/Rome",
    "GB": "Europe/London",
    "CA": "America/Toronto",
    "JP": "Asia/Tokyo",
}


@dataclass
class TripWriteResult:
    """Result of a trip write operation."""
    success: bool
    trip_id: UUID | None = None
    trip: Trip | None = None
    error: str | None = None


def get_trip_by_id(db: Session, trip_id: UUID) -> Trip | None:
    """Get trip by ID."""
    return db.query(Trip).filter(Trip.id == trip_id).first()


def get_user_trips(
    db: Session,
    user_id: UUID,
    status: str | None = None,
    active_only: bool = False
) -> list[Trip]:
    """
    Get trips for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        status: Optional status filter (active, completed, cancelled)
        active_only: Only return active trips
        
    Returns:
        List of Trip objects
    """
    query = db.query(Trip).filter(Trip.user_id == user_id)
    
    if status:
        query = query.filter(Trip.status == status)
    
    if active_only:
        query = query.filter(Trip.is_active == True)
    
    return query.order_by(Trip.start_date.desc()).all()


def get_current_trip(db: Session, user_id: UUID) -> Trip | None:
    """
    Get the current active trip for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Current Trip or None
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.current_trip_id:
        return get_trip_by_id(db, user.current_trip_id)
    return None


def create_trip(
    db: Session,
    user_id: UUID,
    name: str,
    start_date: date,
    destination_country: str,
    end_date: date | None = None,
    destination_city: str | None = None,
    local_currency: str | None = None,
    timezone: str | None = None,
    description: str | None = None,
    set_as_current: bool = True,
) -> TripWriteResult:
    """
    Create a new trip.
    
    Args:
        db: Database session
        user_id: User UUID
        name: Trip name (e.g., "Ecuador Adventure")
        start_date: Trip start date
        destination_country: ISO 3166-1 alpha-2 country code
        end_date: Optional end date
        destination_city: Optional city name
        local_currency: Local currency (auto-detected if not provided)
        timezone: Trip timezone (auto-detected if not provided)
        description: Optional description
        set_as_current: Whether to set this as the user's current trip
        
    Returns:
        TripWriteResult with trip_id and trip object
    """
    try:
        # Normalize country code
        country = destination_country.upper()[:2]
        
        # Auto-detect currency if not provided
        if not local_currency:
            local_currency = COUNTRY_CURRENCIES.get(country, "USD")
        
        # Auto-detect timezone if not provided
        if not timezone:
            timezone = COUNTRY_TIMEZONES.get(country, "UTC")
        
        # Create trip
        trip = Trip(
            user_id=user_id,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            destination_country=country,
            destination_city=destination_city,
            local_currency=local_currency,
            timezone=timezone,
            is_active=True,
            status="active",
        )
        
        db.add(trip)
        db.flush()  # Get the ID
        
        # Set as current trip if requested
        if set_as_current:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.travel_mode_active = True
                user.current_trip_id = trip.id
        
        # Ensure user has a default account
        _ensure_default_account(db, user_id)
        
        db.commit()
        db.refresh(trip)
        
        logger.info(
            "trip_created",
            trip_id=str(trip.id),
            user_id=str(user_id),
            name=name,
            destination=country
        )
        
        return TripWriteResult(
            success=True,
            trip_id=trip.id,
            trip=trip
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_trip_failed", user_id=str(user_id), error=str(e), exc_info=True)
        return TripWriteResult(success=False, error=str(e))


def update_trip(
    db: Session,
    trip_id: UUID,
    **updates: Any
) -> TripWriteResult:
    """
    Update trip fields.
    
    Args:
        db: Database session
        trip_id: Trip UUID
        **updates: Fields to update
        
    Returns:
        TripWriteResult
    """
    try:
        trip = get_trip_by_id(db, trip_id)
        if not trip:
            return TripWriteResult(success=False, error="Trip not found")
        
        allowed_fields = {
            "name", "description", "start_date", "end_date",
            "destination_country", "destination_city",
            "local_currency", "timezone", "status", "is_active"
        }
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(trip, field):
                setattr(trip, field, value)
        
        trip.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(trip)
        
        logger.info(
            "trip_updated",
            trip_id=str(trip_id),
            fields=list(updates.keys())
        )
        
        return TripWriteResult(success=True, trip_id=trip_id, trip=trip)
        
    except Exception as e:
        db.rollback()
        logger.error("update_trip_failed", trip_id=str(trip_id), error=str(e))
        return TripWriteResult(success=False, error=str(e))


def complete_trip(db: Session, trip_id: UUID) -> TripWriteResult:
    """
    Mark a trip as completed.
    
    Args:
        db: Database session
        trip_id: Trip UUID
        
    Returns:
        TripWriteResult
    """
    try:
        trip = get_trip_by_id(db, trip_id)
        if not trip:
            return TripWriteResult(success=False, error="Trip not found")
        
        trip.status = "completed"
        trip.is_active = False
        trip.end_date = trip.end_date or date.today()
        trip.updated_at = datetime.utcnow()
        
        # Deactivate travel mode if this was the current trip
        user = db.query(User).filter(User.id == trip.user_id).first()
        if user and user.current_trip_id == trip_id:
            user.travel_mode_active = False
            user.current_trip_id = None
        
        db.commit()
        
        logger.info("trip_completed", trip_id=str(trip_id))
        
        return TripWriteResult(success=True, trip_id=trip_id, trip=trip)
        
    except Exception as e:
        db.rollback()
        logger.error("complete_trip_failed", trip_id=str(trip_id), error=str(e))
        return TripWriteResult(success=False, error=str(e))


def cancel_trip(db: Session, trip_id: UUID) -> TripWriteResult:
    """
    Cancel a trip.
    
    Args:
        db: Database session
        trip_id: Trip UUID
        
    Returns:
        TripWriteResult
    """
    try:
        trip = get_trip_by_id(db, trip_id)
        if not trip:
            return TripWriteResult(success=False, error="Trip not found")
        
        trip.status = "cancelled"
        trip.is_active = False
        trip.updated_at = datetime.utcnow()
        
        # Deactivate travel mode if this was the current trip
        user = db.query(User).filter(User.id == trip.user_id).first()
        if user and user.current_trip_id == trip_id:
            user.travel_mode_active = False
            user.current_trip_id = None
        
        db.commit()
        
        logger.info("trip_cancelled", trip_id=str(trip_id))
        
        return TripWriteResult(success=True, trip_id=trip_id, trip=trip)
        
    except Exception as e:
        db.rollback()
        logger.error("cancel_trip_failed", trip_id=str(trip_id), error=str(e))
        return TripWriteResult(success=False, error=str(e))


def _ensure_default_account(db: Session, user_id: UUID) -> Account:
    """
    Ensure user has a default account. Creates one if needed.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Default Account
    """
    account = db.query(Account).filter(
        Account.user_id == user_id,
        Account.is_default == True
    ).first()
    
    if account:
        return account
    
    # Get user's home currency
    user = db.query(User).filter(User.id == user_id).first()
    currency = user.home_currency if user else "USD"
    
    # Create default cash account
    account = Account(
        user_id=user_id,
        name="Efectivo",
        account_type="cash",
        currency=currency,
        is_active=True,
        is_default=True,
    )
    
    db.add(account)
    db.flush()
    
    logger.info(
        "default_account_created",
        user_id=str(user_id),
        account_id=str(account.id)
    )
    
    return account


def get_country_info(country_code: str) -> dict:
    """
    Get country information including currency and timezone.
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        
    Returns:
        Dict with currency and timezone
    """
    code = country_code.upper()[:2]
    return {
        "country_code": code,
        "currency": COUNTRY_CURRENCIES.get(code, "USD"),
        "timezone": COUNTRY_TIMEZONES.get(code, "UTC"),
    }

