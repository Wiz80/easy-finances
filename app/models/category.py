"""Category model for expense classification."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.expense import Expense


class Category(Base):
    """
    Category for expense classification.
    MVP categories: DELIVERY, IN HOUSE FOOD, OUT HOUSE FOOD, LODGING, TRANSPORT, TOURISM, HEALTHCARE, MISC
    """

    __tablename__ = "category"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Category Info
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # lowercase, e.g., "food", "lodging"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Classification hints (for LLM)
    keywords: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Comma-separated keywords
    
    # Display
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # emoji or icon name
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # hex color
    
    # Ordering
    sort_order: Mapped[int] = mapped_column(default=0)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name}, slug={self.slug})>"

