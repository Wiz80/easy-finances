"""Add classification feedback table for ML model fine-tuning.

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2026-01-30 12:00:00.000000

This migration adds:
- classification_feedback table for storing category corrections
- Used to collect training data for fine-tuning the expense classifier
"""

from datetime import datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create classification_feedback table."""
    op.create_table(
        "classification_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
        ),
        # Foreign key to expense (optional - feedback can exist without expense)
        sa.Column(
            "expense_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # User who provided the feedback
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Classification data
        sa.Column(
            "predicted_category",
            sa.String(100),
            nullable=False,
            comment="Category predicted by the model",
        ),
        sa.Column(
            "correct_category",
            sa.String(100),
            nullable=False,
            comment="Correct category provided by user",
        ),
        sa.Column(
            "prediction_confidence",
            sa.Numeric(4, 3),
            nullable=True,
            comment="Model confidence score (0.000-1.000)",
        ),
        # Input data for training
        sa.Column(
            "description",
            sa.Text,
            nullable=False,
            comment="Original expense description",
        ),
        sa.Column(
            "merchant",
            sa.String(255),
            nullable=True,
            comment="Merchant name if available",
        ),
        # Metadata
        sa.Column(
            "prediction_source",
            sa.String(50),
            nullable=True,
            comment="Source of prediction: llm, ml_classifier, zero_shot, etc.",
        ),
        sa.Column(
            "model_name",
            sa.String(255),
            nullable=True,
            comment="Name of the model used for prediction",
        ),
        sa.Column(
            "is_correct",
            sa.Boolean,
            nullable=False,
            default=False,
            comment="Whether prediction matched correct category",
        ),
        # Training status
        sa.Column(
            "used_for_training",
            sa.Boolean,
            nullable=False,
            default=False,
            comment="Whether this feedback has been used in model training",
        ),
        sa.Column(
            "training_batch_id",
            sa.String(100),
            nullable=True,
            comment="ID of the training batch that used this feedback",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            default=datetime.utcnow,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        ),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_classification_feedback_is_correct",
        "classification_feedback",
        ["is_correct"],
    )
    op.create_index(
        "ix_classification_feedback_used_for_training",
        "classification_feedback",
        ["used_for_training"],
    )
    op.create_index(
        "ix_classification_feedback_predicted_category",
        "classification_feedback",
        ["predicted_category"],
    )
    op.create_index(
        "ix_classification_feedback_correct_category",
        "classification_feedback",
        ["correct_category"],
    )


def downgrade() -> None:
    """Drop classification_feedback table."""
    op.drop_index("ix_classification_feedback_correct_category")
    op.drop_index("ix_classification_feedback_predicted_category")
    op.drop_index("ix_classification_feedback_used_for_training")
    op.drop_index("ix_classification_feedback_is_correct")
    op.drop_table("classification_feedback")

