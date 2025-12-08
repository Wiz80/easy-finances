"""Card model for credit/debit cards linked to accounts."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.budget import BudgetFundingSource
    from app.models.expense import Expense


class Card(Base):
    """
    Card represents a credit or debit card linked to an account.
    Used for card-based expense tracking and nightly confirmations.
    """

    __tablename__ = "card"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    
    # Card Info
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g., "Visa Gold", "Mastercard Travel"
    card_type: Mapped[str] = mapped_column(String(50), nullable=False)  # credit, debit
    network: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # visa, mastercard, amex
    last_four_digits: Mapped[str] = mapped_column(String(4), nullable=False)
    
    # Optional metadata
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)  # for UI
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="cards")
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="card", cascade="all, delete-orphan"
    )
    budget_funding_sources: Mapped[list["BudgetFundingSource"]] = relationship(
        "BudgetFundingSource", back_populates="card"
    )

    def __repr__(self) -> str:
        return f"<Card(id={self.id}, name={self.name}, last_four={self.last_four_digits})>"

