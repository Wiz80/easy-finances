"""Account model for managing user accounts (bank accounts, wallets, etc)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.expense import Expense
    from app.models.user import User


class Account(Base):
    """
    Account represents a financial account (bank account, cash wallet, etc).
    Used to track where money comes from for expenses.
    """

    __tablename__ = "account"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    
    # Account Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # checking, savings, cash, credit
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    
    # Optional metadata
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_four_digits: Mapped[str | None] = mapped_column(String(4), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    cards: Mapped[list["Card"]] = relationship(
        "Card", back_populates="account", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name={self.name}, type={self.account_type})>"

