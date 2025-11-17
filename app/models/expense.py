"""Expense model - core table for expense tracking."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.card import Card
    from app.models.category import Category
    from app.models.receipt import Receipt
    from app.models.trip import Trip
    from app.models.user import User


class Expense(Base):
    """
    Core expense record with multi-modal input support.
    Supports text, voice, and receipt-based expense capture.
    """

    __tablename__ = "expense"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Foreign Keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id", ondelete="RESTRICT"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip.id", ondelete="SET NULL"), nullable=True
    )
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("card.id", ondelete="SET NULL"), nullable=True
    )
    
    # Amount & Currency (Original)
    amount_original: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    currency_original: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    
    # Expense Details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Payment Method
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # cash, card, transfer
    
    # Extraction Metadata
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # text, audio, image, receipt
    source_meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # msg_id, confidence, etc.
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    
    # Status & Confirmation
    status: Mapped[str] = mapped_column(
        String(50), default="pending_confirm"
    )  # pending_confirm, confirmed, flagged
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="expenses")
    account: Mapped["Account"] = relationship("Account", back_populates="expenses")
    category: Mapped["Category"] = relationship("Category", back_populates="expenses")
    trip: Mapped["Trip | None"] = relationship("Trip", back_populates="expenses")
    card: Mapped["Card | None"] = relationship("Card", back_populates="expenses")
    receipt: Mapped["Receipt | None"] = relationship(
        "Receipt", back_populates="expense", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Expense(id={self.id}, amount={self.amount_original} {self.currency_original}, "
            f"description={self.description[:30]})>"
        )

