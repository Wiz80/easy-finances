"""
Expense writer module for persisting extracted expense data.
Handles idempotency via source_meta (msg_id or content hash).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.expense import Expense
from app.schemas.extraction import ExtractedExpense
from app.storage.category_mapper import map_category_candidate

logger = get_logger(__name__)


@dataclass
class ExpenseWriteResult:
    """Result of an expense write operation."""
    
    expense: Expense
    created: bool  # True if newly created, False if duplicate found
    duplicate_reason: str | None = None  # If duplicate, why


def _build_source_meta(
    extracted: ExtractedExpense,
    msg_id: str | None = None,
    content_hash: str | None = None,
) -> dict:
    """
    Build source_meta JSONB with extraction metadata.
    
    Args:
        extracted: Extracted expense data
        msg_id: Optional message ID for idempotency
        content_hash: Optional content hash for idempotency
        
    Returns:
        dict with source metadata
    """
    meta = {
        "confidence": extracted.confidence,
        "raw_input": extracted.raw_input,
        "card_hint": extracted.card_hint,
    }
    
    if msg_id:
        meta["msg_id"] = msg_id
    if content_hash:
        meta["content_hash"] = content_hash
        
    return meta


def _find_duplicate_expense(
    session: Session,
    user_id: UUID,
    msg_id: str | None = None,
    content_hash: str | None = None,
) -> Expense | None:
    """
    Check for duplicate expense by msg_id or content_hash.
    
    Args:
        session: Database session
        user_id: User ID to scope the search
        msg_id: Optional message ID
        content_hash: Optional content hash
        
    Returns:
        Existing Expense if duplicate found, None otherwise
    """
    if not msg_id and not content_hash:
        return None
    
    query = session.query(Expense).filter(Expense.user_id == user_id)
    
    # Check by msg_id first (exact match in JSONB)
    if msg_id:
        existing = query.filter(
            Expense.source_meta["msg_id"].astext == msg_id
        ).first()
        if existing:
            logger.info(
                "duplicate_expense_found",
                reason="msg_id",
                msg_id=msg_id,
                expense_id=str(existing.id),
            )
            return existing
    
    # Check by content_hash
    if content_hash:
        existing = query.filter(
            Expense.source_meta["content_hash"].astext == content_hash
        ).first()
        if existing:
            logger.info(
                "duplicate_expense_found",
                reason="content_hash",
                hash=content_hash[:16],
                expense_id=str(existing.id),
            )
            return existing
    
    return None


def create_expense(
    session: Session,
    extracted: ExtractedExpense,
    user_id: UUID,
    account_id: UUID,
    source_type: str,
    trip_id: UUID | None = None,
    card_id: UUID | None = None,
    msg_id: str | None = None,
    content_hash: str | None = None,
    occurred_at_override: datetime | None = None,
) -> ExpenseWriteResult:
    """
    Create an expense record from extracted data with idempotency.
    
    This function handles:
    - Duplicate detection via msg_id or content_hash
    - Category mapping from candidate string to category_id
    - Status set to pending_confirm by default
    
    Args:
        session: Database session
        extracted: ExtractedExpense data from extraction tools
        user_id: User ID who owns this expense
        account_id: Account ID for this expense
        source_type: Source type (text, audio, image, receipt)
        trip_id: Optional trip ID
        card_id: Optional card ID
        msg_id: Optional message ID for idempotency
        content_hash: Optional content hash for idempotency
        occurred_at_override: Optional override for occurred_at timestamp
        
    Returns:
        ExpenseWriteResult with expense and creation status
        
    Example:
        >>> result = create_expense(
        ...     session=db,
        ...     extracted=extracted_expense,
        ...     user_id=user.id,
        ...     account_id=account.id,
        ...     source_type="text",
        ...     msg_id="wa_msg_123"
        ... )
        >>> if result.created:
        ...     print(f"New expense: {result.expense.id}")
        ... else:
        ...     print(f"Duplicate: {result.duplicate_reason}")
    """
    logger.debug(
        "creating_expense",
        user_id=str(user_id),
        amount=float(extracted.amount),
        currency=extracted.currency,
        source_type=source_type,
        msg_id=msg_id,
    )
    
    # Check for duplicates
    existing = _find_duplicate_expense(
        session=session,
        user_id=user_id,
        msg_id=msg_id,
        content_hash=content_hash,
    )
    
    if existing:
        duplicate_reason = "msg_id" if msg_id else "content_hash"
        logger.info(
            "expense_duplicate_returned",
            expense_id=str(existing.id),
            reason=duplicate_reason,
        )
        return ExpenseWriteResult(
            expense=existing,
            created=False,
            duplicate_reason=duplicate_reason,
        )
    
    # Map category candidate to category_id
    category_id = map_category_candidate(session, extracted.category_candidate)
    
    # Build source_meta
    source_meta = _build_source_meta(
        extracted=extracted,
        msg_id=msg_id,
        content_hash=content_hash,
    )
    
    # Determine occurred_at: override > extracted > now
    occurred_at = occurred_at_override or extracted.occurred_at or datetime.utcnow()
    
    # Create expense record
    expense = Expense(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        trip_id=trip_id,
        card_id=card_id,
        amount_original=extracted.amount,
        currency_original=extracted.currency,
        description=extracted.description,
        merchant=extracted.merchant,
        occurred_at=occurred_at,
        method=extracted.method,
        source_type=source_type,
        source_meta=source_meta,
        confidence_score=extracted.confidence,
        status="pending_confirm",
        notes=extracted.notes,
    )
    
    session.add(expense)
    session.flush()  # Get the ID without committing
    
    logger.info(
        "expense_created",
        expense_id=str(expense.id),
        user_id=str(user_id),
        amount=float(expense.amount_original),
        currency=expense.currency_original,
        category_id=str(category_id),
        source_type=source_type,
        confidence=expense.confidence_score,
    )
    
    return ExpenseWriteResult(expense=expense, created=True)


def update_expense_status(
    session: Session,
    expense_id: UUID,
    status: str,
    confirmed_at: datetime | None = None,
) -> Expense:
    """
    Update expense status (e.g., pending_confirm → confirmed).
    
    Args:
        session: Database session
        expense_id: Expense ID to update
        status: New status (pending_confirm, confirmed, flagged)
        confirmed_at: Optional confirmation timestamp
        
    Returns:
        Updated Expense object
        
    Raises:
        ValueError: If expense not found
    """
    expense = session.query(Expense).filter(Expense.id == expense_id).first()
    
    if not expense:
        logger.error("expense_not_found", expense_id=str(expense_id))
        raise ValueError(f"Expense not found: {expense_id}")
    
    old_status = expense.status
    expense.status = status
    
    if status == "confirmed" and confirmed_at:
        expense.confirmed_at = confirmed_at
    elif status == "confirmed" and not confirmed_at:
        expense.confirmed_at = datetime.utcnow()
    
    session.flush()
    
    logger.info(
        "expense_status_updated",
        expense_id=str(expense_id),
        old_status=old_status,
        new_status=status,
    )
    
    return expense


def get_expense_by_id(session: Session, expense_id: UUID) -> Expense | None:
    """
    Get expense by ID.
    
    Args:
        session: Database session
        expense_id: Expense ID
        
    Returns:
        Expense object or None if not found
    """
    return session.query(Expense).filter(Expense.id == expense_id).first()


def get_pending_expenses(
    session: Session,
    user_id: UUID,
    method: str | None = None,
) -> list[Expense]:
    """
    Get expenses pending confirmation for a user.
    
    Args:
        session: Database session
        user_id: User ID
        method: Optional filter by payment method (cash, card)
        
    Returns:
        List of pending expenses
    """
    query = session.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.status == "pending_confirm",
    )
    
    if method:
        query = query.filter(Expense.method == method)
    
    return query.order_by(Expense.occurred_at.desc()).all()

