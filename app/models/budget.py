"""Budget models for trip and date-range budgeting with category allocations."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.card import Card
    from app.models.category import Category
    from app.models.trip import Trip
    from app.models.user import User


class Budget(Base):
    """
    Budget for a date range with category allocations and funding sources.
    
    Allows tracking spending against planned amounts per category.
    Can be optionally scoped to a specific trip.
    
    Example:
        - "Ecuador Trip Budget": Dec 15-30, total $5,000,000 COP
        - "December 2024 Budget": Dec 1-31, total $3,000 USD
    """

    __tablename__ = "budget"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip.id", ondelete="SET NULL"), nullable=True
    )

    # Budget Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Budget Period
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Total Budget Amount
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, completed, cancelled

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="budgets")
    trip: Mapped["Trip | None"] = relationship("Trip", back_populates="budgets")
    allocations: Mapped[list["BudgetAllocation"]] = relationship(
        "BudgetAllocation", back_populates="budget", cascade="all, delete-orphan"
    )
    funding_sources: Mapped[list["BudgetFundingSource"]] = relationship(
        "BudgetFundingSource", back_populates="budget", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Budget(id={self.id}, name={self.name}, "
            f"total={self.total_amount} {self.currency})>"
        )

    @property
    def total_allocated(self) -> Decimal:
        """Sum of all category allocations."""
        return sum(
            (a.allocated_amount for a in self.allocations), 
            start=Decimal("0")
        )

    @property
    def total_spent(self) -> Decimal:
        """Sum of spent amounts across all allocations."""
        return sum(
            (a.spent_amount for a in self.allocations), 
            start=Decimal("0")
        )

    @property
    def remaining(self) -> Decimal:
        """Remaining budget amount."""
        return self.total_amount - self.total_spent


class BudgetAllocation(Base):
    """
    Category allocation within a budget.
    
    Defines how much of the budget is allocated to a specific category
    and tracks spending against that allocation.
    
    Example:
        - Food: $1,500,000 COP (alert at 80%)
        - Transport: $800,000 COP (alert at 90%)
    """

    __tablename__ = "budget_allocation"
    __table_args__ = (
        UniqueConstraint("budget_id", "category_id", name="uq_budget_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budget.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id", ondelete="RESTRICT"), nullable=False
    )

    # Allocation Amount
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217

    # Spending Tracking (updated as expenses are logged)
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0")
    )

    # Alert Configuration
    alert_threshold_percent: Mapped[int] = mapped_column(
        Integer, default=80
    )  # Alert when X% spent
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    budget: Mapped["Budget"] = relationship("Budget", back_populates="allocations")
    category: Mapped["Category"] = relationship("Category", back_populates="budget_allocations")

    def __repr__(self) -> str:
        return (
            f"<BudgetAllocation(id={self.id}, "
            f"allocated={self.allocated_amount}, spent={self.spent_amount})>"
        )

    @property
    def remaining(self) -> Decimal:
        """Remaining amount in this allocation."""
        return self.allocated_amount - self.spent_amount

    @property
    def percent_used(self) -> float:
        """Percentage of allocation used."""
        if self.allocated_amount == 0:
            return 0.0
        return float(self.spent_amount / self.allocated_amount * 100)

    @property
    def should_alert(self) -> bool:
        """Check if spending has reached alert threshold."""
        return self.percent_used >= self.alert_threshold_percent and not self.alert_sent


class BudgetFundingSource(Base):
    """
    Funding source for a budget - links budget to accounts/cards/cash.
    
    Defines where money for the budget comes from and priority of use.
    
    Example:
        - Primary: Visa Travel card (priority 1, default)
        - Backup: $200 USD cash (priority 2)
    """

    __tablename__ = "budget_funding_source"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budget.id", ondelete="CASCADE"), nullable=False
    )

    # Source Type: "card", "account", "cash"
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # References (mutually exclusive based on source_type)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("card.id", ondelete="SET NULL"), nullable=True
    )

    # For cash sources
    cash_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)  # ISO 4217
    cash_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    cash_spent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2), default=Decimal("0"), nullable=True
    )

    # Priority and Default
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1 = highest priority

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    budget: Mapped["Budget"] = relationship("Budget", back_populates="funding_sources")
    account: Mapped["Account | None"] = relationship(
        "Account", back_populates="budget_funding_sources"
    )
    card: Mapped["Card | None"] = relationship(
        "Card", back_populates="budget_funding_sources"
    )

    def __repr__(self) -> str:
        source_info = self.source_type
        if self.source_type == "cash":
            source_info = f"cash:{self.cash_currency}"
        elif self.source_type == "card" and self.card_id:
            source_info = f"card:{self.card_id}"
        elif self.source_type == "account" and self.account_id:
            source_info = f"account:{self.account_id}"
        return f"<BudgetFundingSource(id={self.id}, type={source_info}, priority={self.priority})>"

    @property
    def cash_remaining(self) -> Decimal | None:
        """Remaining cash if this is a cash source."""
        if self.source_type != "cash" or self.cash_amount is None:
            return None
        return self.cash_amount - (self.cash_spent or Decimal("0"))

