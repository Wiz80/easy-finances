"""Classification feedback model for ML model training data collection."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.user import User


class ClassificationFeedback(Base):
    """
    Stores user corrections on expense category predictions.

    Used to collect training data for fine-tuning the expense classifier.
    When a user corrects an incorrectly categorized expense, we record:
    - What the model predicted
    - What the correct category was
    - The input text that led to the prediction

    This data can then be used to:
    - Evaluate model performance
    - Fine-tune the classifier
    - Improve category mappings
    """

    __tablename__ = "classification_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign Keys
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification Data
    predicted_category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Category predicted by model
    correct_category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Correct category from user
    prediction_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=4, scale=3), nullable=True
    )  # Model confidence (0.000-1.000)

    # Input Data (for training)
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Original expense description
    merchant: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Merchant name if available

    # Metadata
    prediction_source: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # llm, ml_classifier, zero_shot, etc.
    model_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Name of model used
    is_correct: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Whether prediction was correct

    # Training Status
    used_for_training: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Has been used in training
    training_batch_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Training batch ID

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    expense: Mapped["Expense | None"] = relationship("Expense", backref="classification_feedback")
    user: Mapped["User"] = relationship("User", backref="classification_feedbacks")

    def __repr__(self) -> str:
        return (
            f"<ClassificationFeedback(id={self.id}, "
            f"predicted={self.predicted_category}, "
            f"correct={self.correct_category}, "
            f"is_correct={self.is_correct})>"
        )

    @property
    def is_miscategorized(self) -> bool:
        """Check if this represents a miscategorization."""
        return not self.is_correct

    @property
    def training_text(self) -> str:
        """Get the text used for training (description + merchant)."""
        if self.merchant:
            return f"{self.merchant}: {self.description}"
        return self.description

