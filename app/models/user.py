"""User model for authentication and profile management."""

import uuid
from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.budget import Budget
    from app.models.conversation import ConversationState
    from app.models.expense import Expense
    from app.models.trip import Trip


class User(Base):
    """
    Enhanced user model with onboarding, travel mode, and notification preferences.
    
    Supports:
    - WhatsApp-based onboarding flow
    - Travel mode with active trip tracking
    - Notification preferences (daily summary, budget alerts)
    - Conversation state management
    """

    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Identity
    # ─────────────────────────────────────────────────────────────────────────
    phone_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # WhatsApp number with country code, e.g., "+573115084628"
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Preferred name for chat interactions
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Preferences
    # ─────────────────────────────────────────────────────────────────────────
    preferred_language: Mapped[str] = mapped_column(
        String(10), default="es"
    )  # "es", "en"
    home_currency: Mapped[str] = mapped_column(
        String(3), default="USD"
    )  # ISO 4217
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/Mexico_City"
    )  # IANA timezone
    
    # ─────────────────────────────────────────────────────────────────────────
    # Onboarding Status
    # ─────────────────────────────────────────────────────────────────────────
    onboarding_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, in_progress, completed
    onboarding_step: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Current step if in_progress: "name", "currency", "timezone", etc.
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Location
    # ─────────────────────────────────────────────────────────────────────────
    country: Mapped[str | None] = mapped_column(
        String(2), nullable=True
    )  # ISO 3166-1 alpha-2, e.g., "CO", "US", "MX"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Travel Mode
    # ─────────────────────────────────────────────────────────────────────────
    travel_mode_active: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Is user currently in travel mode?
    current_trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("trip.id", ondelete="SET NULL", use_alter=True),
        nullable=True
    )  # Active trip reference
    
    # ─────────────────────────────────────────────────────────────────────────
    # Active Budget (independent of trip)
    # ─────────────────────────────────────────────────────────────────────────
    current_budget_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("budget.id", ondelete="SET NULL", use_alter=True),
        nullable=True
    )  # Currently active budget for expense tracking
    
    # ─────────────────────────────────────────────────────────────────────────
    # Notification Preferences
    # ─────────────────────────────────────────────────────────────────────────
    daily_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_summary_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )  # e.g., 21:00 local time
    budget_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmation_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # ─────────────────────────────────────────────────────────────────────────
    # WhatsApp Integration
    # ─────────────────────────────────────────────────────────────────────────
    whatsapp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    last_whatsapp_interaction: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Timestamps
    # ─────────────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────────────────────
    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="user", cascade="all, delete-orphan"
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip", 
        back_populates="user", 
        cascade="all, delete-orphan",
        foreign_keys="Trip.user_id"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        "Budget", 
        back_populates="user", 
        cascade="all, delete-orphan",
        foreign_keys="Budget.user_id"
    )
    conversations: Mapped[list["ConversationState"]] = relationship(
        "ConversationState", back_populates="user", cascade="all, delete-orphan"
    )
    
    # Current trip relationship (separate from trips list)
    current_trip: Mapped["Trip | None"] = relationship(
        "Trip",
        foreign_keys=[current_trip_id],
        post_update=True
    )
    
    # Current budget relationship (independent of trip)
    current_budget: Mapped["Budget | None"] = relationship(
        "Budget",
        foreign_keys=[current_budget_id],
        post_update=True
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, phone={self.phone_number}, name={self.full_name})>"
    
    @property
    def display_name(self) -> str:
        """Return nickname if set, otherwise full_name."""
        return self.nickname or self.full_name
    
    @property
    def is_onboarding_complete(self) -> bool:
        """Check if user has completed onboarding."""
        return self.onboarding_status == "completed"
    
    @property
    def needs_onboarding(self) -> bool:
        """Check if user needs to complete onboarding."""
        return self.onboarding_status in ("pending", "in_progress")
