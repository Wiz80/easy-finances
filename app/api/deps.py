"""
FastAPI dependencies for dependency injection.

Provides database sessions, authentication, and service instances.
"""

from typing import Annotated, Generator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.integrations.whatsapp import TwilioWhatsAppClient, get_twilio_client
from app.logging_config import get_logger
from app.models import User

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Database Session
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    
    Yields:
        SQLAlchemy Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Type alias for cleaner dependency injection
DbSession = Annotated[Session, Depends(get_db)]


# ─────────────────────────────────────────────────────────────────────────────
# Twilio Client
# ─────────────────────────────────────────────────────────────────────────────

def get_twilio() -> TwilioWhatsAppClient:
    """
    Dependency to get Twilio client.
    
    Returns:
        TwilioWhatsAppClient instance
    """
    return get_twilio_client()


TwilioClient = Annotated[TwilioWhatsAppClient, Depends(get_twilio)]


# ─────────────────────────────────────────────────────────────────────────────
# Twilio Signature Validation
# ─────────────────────────────────────────────────────────────────────────────

async def validate_twilio_signature(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header()] = None,
) -> bool:
    """
    Validate incoming Twilio webhook signature.
    
    In development mode, signature validation can be skipped.
    In production, invalid signatures raise 403.
    
    Args:
        request: FastAPI request object
        x_twilio_signature: Twilio signature header
        
    Returns:
        True if valid (or validation skipped)
        
    Raises:
        HTTPException: 403 if signature invalid in production
    """
    # Skip validation in development if no auth token configured
    if settings.environment == "development" and not settings.twilio_auth_token:
        logger.warning(
            "twilio_signature_validation_skipped",
            reason="Development mode, no auth token"
        )
        return True
    
    if not x_twilio_signature:
        if settings.environment == "production":
            logger.warning("twilio_missing_signature")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing Twilio signature"
            )
        return True
    
    # Get the full URL and form data for validation
    url = str(request.url)
    form_data = await request.form()
    params = {key: value for key, value in form_data.items()}
    
    # Validate using Twilio client
    client = get_twilio_client()
    is_valid = client.validate_webhook_signature(url, params, x_twilio_signature)
    
    if not is_valid and settings.environment == "production":
        logger.warning(
            "twilio_invalid_signature",
            url=url
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )
    
    return is_valid


# ─────────────────────────────────────────────────────────────────────────────
# User Lookup
# ─────────────────────────────────────────────────────────────────────────────

def get_user_by_phone(db: Session, phone_number: str) -> User | None:
    """
    Get user by phone number.
    
    Args:
        db: Database session
        phone_number: Phone number (with or without + prefix)
        
    Returns:
        User or None
    """
    # Normalize phone number
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    return db.query(User).filter(User.phone_number == phone_number).first()


def get_or_create_user(db: Session, phone_number: str, profile_name: str | None = None) -> User:
    """
    Get existing user or create a new one.
    
    Args:
        db: Database session
        phone_number: Phone number
        profile_name: WhatsApp profile name (for new users)
        
    Returns:
        User instance
    """
    user = get_user_by_phone(db, phone_number)
    
    if user:
        return user
    
    # Normalize phone number
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    # Create new user with pending onboarding
    user = User(
        phone_number=phone_number,
        full_name=profile_name or "Usuario",
        nickname=profile_name,
        onboarding_status="pending",
        whatsapp_verified=True,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(
        "user_created",
        user_id=str(user.id),
        phone=phone_number[-4:]  # Last 4 digits for privacy
    )
    
    return user

