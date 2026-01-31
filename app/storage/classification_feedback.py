"""
Storage operations for classification feedback.

Handles saving and querying user corrections for expense categorization.
Used to collect training data for fine-tuning the expense classifier.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.classification_feedback import ClassificationFeedback

logger = get_logger(__name__)


async def save_classification_feedback(
    db: AsyncSession,
    user_id: uuid.UUID,
    predicted_category: str,
    correct_category: str,
    description: str,
    merchant: str | None = None,
    expense_id: uuid.UUID | None = None,
    prediction_confidence: float | None = None,
    prediction_source: str | None = None,
    model_name: str | None = None,
) -> ClassificationFeedback:
    """
    Save classification feedback for future model training.

    Args:
        db: Database session
        user_id: User who provided the feedback
        predicted_category: Category predicted by the model
        correct_category: Correct category provided by user
        description: Original expense description
        merchant: Merchant name if available
        expense_id: Related expense ID if available
        prediction_confidence: Model confidence score
        prediction_source: Source of prediction (llm, ml_classifier, etc.)
        model_name: Name of the model used

    Returns:
        Created ClassificationFeedback record
    """
    is_correct = predicted_category.lower() == correct_category.lower()

    feedback = ClassificationFeedback(
        user_id=user_id,
        expense_id=expense_id,
        predicted_category=predicted_category,
        correct_category=correct_category,
        description=description,
        merchant=merchant,
        prediction_confidence=Decimal(str(prediction_confidence)) if prediction_confidence else None,
        prediction_source=prediction_source,
        model_name=model_name,
        is_correct=is_correct,
        used_for_training=False,
    )

    db.add(feedback)
    await db.flush()

    logger.info(
        "classification_feedback_saved",
        feedback_id=str(feedback.id),
        user_id=str(user_id),
        predicted=predicted_category,
        correct=correct_category,
        is_correct=is_correct,
    )

    return feedback


async def get_training_data(
    db: AsyncSession,
    limit: int = 1000,
    exclude_used: bool = True,
    only_incorrect: bool = False,
) -> Sequence[ClassificationFeedback]:
    """
    Get feedback records for model training.

    Args:
        db: Database session
        limit: Maximum number of records to return
        exclude_used: Exclude records already used in training
        only_incorrect: Only include miscategorized records

    Returns:
        List of ClassificationFeedback records
    """
    conditions = []

    if exclude_used:
        conditions.append(ClassificationFeedback.used_for_training == False)  # noqa: E712

    if only_incorrect:
        conditions.append(ClassificationFeedback.is_correct == False)  # noqa: E712

    query = select(ClassificationFeedback)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(ClassificationFeedback.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def mark_as_used_for_training(
    db: AsyncSession,
    feedback_ids: list[uuid.UUID],
    training_batch_id: str,
) -> int:
    """
    Mark feedback records as used in a training batch.

    Args:
        db: Database session
        feedback_ids: List of feedback IDs to mark
        training_batch_id: ID of the training batch

    Returns:
        Number of records updated
    """
    from sqlalchemy import update

    result = await db.execute(
        update(ClassificationFeedback)
        .where(ClassificationFeedback.id.in_(feedback_ids))
        .values(
            used_for_training=True,
            training_batch_id=training_batch_id,
            updated_at=datetime.utcnow(),
        )
    )

    updated_count = result.rowcount
    logger.info(
        "feedback_marked_for_training",
        count=updated_count,
        batch_id=training_batch_id,
    )

    return updated_count


async def get_category_accuracy_stats(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> dict[str, dict]:
    """
    Get accuracy statistics per category.

    Args:
        db: Database session
        user_id: Optional user ID to filter by

    Returns:
        Dict with stats per category
    """
    base_query = select(
        ClassificationFeedback.predicted_category,
        func.count().label("total"),
        func.sum(func.cast(ClassificationFeedback.is_correct, type_=int)).label("correct"),
    ).group_by(ClassificationFeedback.predicted_category)

    if user_id:
        base_query = base_query.where(ClassificationFeedback.user_id == user_id)

    result = await db.execute(base_query)
    rows = result.all()

    stats = {}
    for row in rows:
        category = row.predicted_category
        total = row.total
        correct = row.correct or 0
        accuracy = correct / total if total > 0 else 0

        stats[category] = {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": round(accuracy, 4),
        }

    return stats


async def get_common_miscategorizations(
    db: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """
    Get most common miscategorization patterns.

    Returns pairs of (predicted, correct) categories sorted by frequency.

    Args:
        db: Database session
        limit: Maximum number of patterns to return

    Returns:
        List of dicts with pattern info
    """
    query = (
        select(
            ClassificationFeedback.predicted_category,
            ClassificationFeedback.correct_category,
            func.count().label("count"),
        )
        .where(ClassificationFeedback.is_correct == False)  # noqa: E712
        .group_by(
            ClassificationFeedback.predicted_category,
            ClassificationFeedback.correct_category,
        )
        .order_by(func.count().desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    patterns = []
    for row in rows:
        patterns.append({
            "predicted": row.predicted_category,
            "correct": row.correct_category,
            "count": row.count,
        })

    return patterns


async def export_training_dataset(
    db: AsyncSession,
    format: str = "jsonl",
) -> list[dict]:
    """
    Export feedback data in a format suitable for training.

    Args:
        db: Database session
        format: Output format (jsonl, csv)

    Returns:
        List of training examples
    """
    feedback_records = await get_training_data(
        db,
        limit=10000,
        exclude_used=False,
        only_incorrect=False,
    )

    dataset = []
    for record in feedback_records:
        example = {
            "text": record.training_text,
            "label": record.correct_category,
            "original_prediction": record.predicted_category,
            "was_correct": record.is_correct,
            "merchant": record.merchant,
        }
        dataset.append(example)

    logger.info(
        "training_dataset_exported",
        total_examples=len(dataset),
        format=format,
    )

    return dataset

