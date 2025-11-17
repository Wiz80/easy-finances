"""Trip model for travel mode expense tracking."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.user import User


class Trip(Base):
    """
    Trip represents a travel period for Travel Mode expense tracking.
    Scopes budgets, FX snapshots, and expense grouping.
    """

    __tablename__ = "trip"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    
    # Trip Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Dates
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Location
    destination_country: Mapped[str] = mapped_column(
        String(2), nullable=False
    )  # ISO 3166-1 alpha-2
    destination_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, completed, cancelled
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trips")
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="trip", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Trip(id={self.id}, name={self.name}, destination={self.destination_country})>"

