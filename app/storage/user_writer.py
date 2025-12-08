"""
User storage operations for the Configuration Agent.

Handles user creation, updates, and onboarding state management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import User

logger = get_logger(__name__)


@dataclass
class UserWriteResult:
    """Result of a user write operation."""
    success: bool
    user_id: UUID | None = None
    is_new: bool = False
    error: str | None = None


def get_user_by_phone(db: Session, phone_number: str) -> User | None:
    """
    Get user by phone number.
    
    Args:
        db: Database session
        phone_number: Phone number with country code (e.g., "+573115084628")
        
    Returns:
        User or None if not found
    """
    return db.query(User).filter(User.phone_number == phone_number).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """
    Get user by ID.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        User or None if not found
    """
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    phone_number: str,
    full_name: str = "Usuario",
    nickname: str | None = None,
    home_currency: str = "USD",
    timezone: str = "America/Mexico_City",
    preferred_language: str = "es",
) -> UserWriteResult:
    """
    Create a new user.
    
    Args:
        db: Database session
        phone_number: Phone number with country code
        full_name: User's full name
        nickname: Optional nickname
        home_currency: Home currency code (ISO 4217)
        timezone: IANA timezone
        preferred_language: Language preference (es, en)
        
    Returns:
        UserWriteResult with success status and user_id
    """
    try:
        # Check if user already exists
        existing = get_user_by_phone(db, phone_number)
        if existing:
            logger.warning(
                "user_already_exists",
                phone=phone_number[-4:],
                user_id=str(existing.id)
            )
            return UserWriteResult(
                success=True,
                user_id=existing.id,
                is_new=False
            )
        
        # Create new user
        user = User(
            phone_number=phone_number,
            full_name=full_name,
            nickname=nickname or full_name.split()[0],
            home_currency=home_currency,
            timezone=timezone,
            preferred_language=preferred_language,
            onboarding_status="pending",
            whatsapp_verified=True,
            whatsapp_verified_at=datetime.utcnow(),
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(
            "user_created",
            user_id=str(user.id),
            phone=phone_number[-4:]
        )
        
        return UserWriteResult(
            success=True,
            user_id=user.id,
            is_new=True
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_user_failed", error=str(e), exc_info=True)
        return UserWriteResult(success=False, error=str(e))


def update_user(
    db: Session,
    user_id: UUID,
    **updates: Any
) -> UserWriteResult:
    """
    Update user fields.
    
    Args:
        db: Database session
        user_id: User UUID
        **updates: Fields to update (full_name, nickname, home_currency, etc.)
        
    Returns:
        UserWriteResult
        
    Example:
        update_user(db, user_id, full_name="Harrison", home_currency="COP")
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return UserWriteResult(success=False, error="User not found")
        
        # Allowed fields to update
        allowed_fields = {
            "full_name", "nickname", "email", "home_currency", "timezone",
            "preferred_language", "onboarding_status", "onboarding_step",
            "travel_mode_active", "current_trip_id",
            "daily_summary_enabled", "daily_summary_time",
            "budget_alerts_enabled", "confirmation_reminders_enabled",
        }
        
        updated_fields = []
        for field, value in updates.items():
            if field in allowed_fields and hasattr(user, field):
                setattr(user, field, value)
                updated_fields.append(field)
        
        user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            "user_updated",
            user_id=str(user_id),
            fields=updated_fields
        )
        
        return UserWriteResult(success=True, user_id=user_id)
        
    except Exception as e:
        db.rollback()
        logger.error("update_user_failed", user_id=str(user_id), error=str(e))
        return UserWriteResult(success=False, error=str(e))


def complete_onboarding(
    db: Session,
    user_id: UUID,
    full_name: str | None = None,
    nickname: str | None = None,
    home_currency: str | None = None,
    timezone: str | None = None,
) -> UserWriteResult:
    """
    Complete user onboarding with final data.
    
    Args:
        db: Database session
        user_id: User UUID
        full_name: Final name (optional if already set)
        nickname: Nickname (optional)
        home_currency: Home currency (optional if already set)
        timezone: Timezone (optional if already set)
        
    Returns:
        UserWriteResult
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return UserWriteResult(success=False, error="User not found")
        
        # Update provided fields
        if full_name:
            user.full_name = full_name
        if nickname:
            user.nickname = nickname
        if home_currency:
            user.home_currency = home_currency
        if timezone:
            user.timezone = timezone
        
        # Mark onboarding complete
        user.onboarding_status = "completed"
        user.onboarding_step = None
        user.onboarding_completed_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(
            "onboarding_completed",
            user_id=str(user_id),
            currency=user.home_currency,
            timezone=user.timezone
        )
        
        return UserWriteResult(success=True, user_id=user_id)
        
    except Exception as e:
        db.rollback()
        logger.error("complete_onboarding_failed", user_id=str(user_id), error=str(e))
        return UserWriteResult(success=False, error=str(e))


def set_onboarding_step(
    db: Session,
    user_id: UUID,
    step: str
) -> UserWriteResult:
    """
    Update onboarding step for tracking progress.
    
    Args:
        db: Database session
        user_id: User UUID
        step: Step name (e.g., "name", "currency", "timezone")
        
    Returns:
        UserWriteResult
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return UserWriteResult(success=False, error="User not found")
        
        user.onboarding_status = "in_progress"
        user.onboarding_step = step
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        return UserWriteResult(success=True, user_id=user_id)
        
    except Exception as e:
        db.rollback()
        logger.error("set_onboarding_step_failed", user_id=str(user_id), error=str(e))
        return UserWriteResult(success=False, error=str(e))


def activate_travel_mode(
    db: Session,
    user_id: UUID,
    trip_id: UUID
) -> UserWriteResult:
    """
    Activate travel mode and set current trip.
    
    Args:
        db: Database session
        user_id: User UUID
        trip_id: Trip UUID to activate
        
    Returns:
        UserWriteResult
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return UserWriteResult(success=False, error="User not found")
        
        user.travel_mode_active = True
        user.current_trip_id = trip_id
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(
            "travel_mode_activated",
            user_id=str(user_id),
            trip_id=str(trip_id)
        )
        
        return UserWriteResult(success=True, user_id=user_id)
        
    except Exception as e:
        db.rollback()
        logger.error("activate_travel_mode_failed", user_id=str(user_id), error=str(e))
        return UserWriteResult(success=False, error=str(e))


def deactivate_travel_mode(db: Session, user_id: UUID) -> UserWriteResult:
    """
    Deactivate travel mode.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        UserWriteResult
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return UserWriteResult(success=False, error="User not found")
        
        user.travel_mode_active = False
        user.current_trip_id = None
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info("travel_mode_deactivated", user_id=str(user_id))
        
        return UserWriteResult(success=True, user_id=user_id)
        
    except Exception as e:
        db.rollback()
        logger.error("deactivate_travel_mode_failed", user_id=str(user_id), error=str(e))
        return UserWriteResult(success=False, error=str(e))

