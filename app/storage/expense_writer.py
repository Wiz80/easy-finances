"""
Expense writer module for persisting extracted expense data.
Handles idempotency via source_meta (msg_id or content hash).
Supports budget synchronization when user has an active budget.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.expense import Expense
from app.models.user import User
from app.models.budget import Budget, BudgetAllocation
from app.models.category import Category
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
    
    # Handle installments
    installments_total = getattr(extracted, 'installments', 1) or 1
    installment_amount = None
    total_debt_amount = None
    
    if installments_total > 1:
        # Calculate installment amount (amount per payment)
        installment_amount = (extracted.amount / Decimal(installments_total)).quantize(
            Decimal("0.01")
        )
        # Total debt is the full purchase amount
        total_debt_amount = extracted.amount
        
        logger.info(
            "installment_expense_detected",
            total=float(extracted.amount),
            installments=installments_total,
            per_installment=float(installment_amount),
        )
    
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
        # Installment fields
        installments_total=installments_total,
        installments_paid=1,  # First installment is paid at purchase
        installment_amount=installment_amount,
        total_debt_amount=total_debt_amount,
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


# ─────────────────────────────────────────────────────────────────────────────
# Budget Synchronization
# ─────────────────────────────────────────────────────────────────────────────

def sync_expense_with_budget(
    session: Session,
    expense: Expense,
    user: User,
) -> dict | None:
    """
    Synchronize expense with user's active budget.
    
    Updates the spent_amount in the appropriate budget allocation.
    If no allocation exists for the expense's category, uses the
    "Gastos Inesperados" (unexpected) allocation.
    
    Args:
        session: Database session
        expense: Expense to sync
        user: User who owns the expense
        
    Returns:
        Dict with sync details or None if no budget active
    """
    if not user.current_budget_id:
        logger.debug(
            "sync_expense_no_budget",
            expense_id=str(expense.id),
            user_id=str(user.id),
        )
        return None
    
    budget = session.query(Budget).filter(
        Budget.id == user.current_budget_id
    ).first()
    
    if not budget or budget.status != "active":
        logger.debug(
            "sync_expense_budget_inactive",
            expense_id=str(expense.id),
            budget_id=str(user.current_budget_id) if user.current_budget_id else None,
        )
        return None
    
    # Find allocation for this expense's category
    allocation = None
    if expense.category_id:
        allocation = session.query(BudgetAllocation).filter(
            BudgetAllocation.budget_id == budget.id,
            BudgetAllocation.category_id == expense.category_id,
        ).first()
    
    # If no allocation for category, use unexpected expenses allocation
    if not allocation:
        unexpected_category = session.query(Category).filter(
            Category.slug.in_(["unexpected_expenses", "misc"])
        ).first()
        
        if unexpected_category:
            allocation = session.query(BudgetAllocation).filter(
                BudgetAllocation.budget_id == budget.id,
                BudgetAllocation.category_id == unexpected_category.id,
            ).first()
    
    if not allocation:
        logger.warning(
            "sync_expense_no_allocation",
            expense_id=str(expense.id),
            budget_id=str(budget.id),
            category_id=str(expense.category_id) if expense.category_id else None,
        )
        return None
    
    # Calculate amount to deduct
    # If currencies differ, we would need FX conversion (Phase 3)
    # For now, assume same currency or add simple logic
    amount_to_deduct = expense.amount_original
    
    # Handle installments: only deduct current installment
    if expense.installments_total and expense.installments_total > 1:
        if expense.installment_amount:
            amount_to_deduct = expense.installment_amount
        else:
            amount_to_deduct = expense.amount_original / expense.installments_total
    
    # Simple currency warning (FX will be added in Phase 3)
    if expense.currency_original != budget.currency:
        logger.warning(
            "sync_expense_currency_mismatch",
            expense_id=str(expense.id),
            expense_currency=expense.currency_original,
            budget_currency=budget.currency,
        )
        # For now, we still add the amount (FX conversion will be Phase 3)
    
    # Update allocation spent amount
    allocation.spent_amount = (allocation.spent_amount or Decimal("0")) + amount_to_deduct
    
    session.flush()
    
    sync_result = {
        "budget_id": str(budget.id),
        "budget_name": budget.name,
        "allocation_id": str(allocation.id),
        "category_id": str(allocation.category_id),
        "amount_deducted": str(amount_to_deduct),
        "new_spent_amount": str(allocation.spent_amount),
        "allocated_amount": str(allocation.allocated_amount),
        "remaining": str(allocation.allocated_amount - allocation.spent_amount),
    }
    
    logger.info(
        "expense_synced_with_budget",
        expense_id=str(expense.id),
        **sync_result,
    )
    
    # Check if alert threshold reached
    if allocation.should_alert:
        logger.info(
            "budget_alert_threshold_reached",
            allocation_id=str(allocation.id),
            percent_used=allocation.percent_used,
            threshold=allocation.alert_threshold_percent,
        )
        sync_result["alert_triggered"] = True
        sync_result["percent_used"] = allocation.percent_used
    
    return sync_result


def create_expense_with_budget_sync(
    session: Session,
    extracted: ExtractedExpense,
    user: User,
    account_id: UUID,
    source_type: str,
    trip_id: UUID | None = None,
    card_id: UUID | None = None,
    msg_id: str | None = None,
    content_hash: str | None = None,
    occurred_at_override: datetime | None = None,
) -> tuple[ExpenseWriteResult, dict | None]:
    """
    Create expense and sync with user's active budget.
    
    This is the preferred method for creating expenses when budget
    tracking is enabled.
    
    Args:
        session: Database session
        extracted: ExtractedExpense data
        user: User model instance
        account_id: Account ID
        source_type: Source type
        trip_id: Optional trip ID
        card_id: Optional card ID
        msg_id: Optional message ID for idempotency
        content_hash: Optional content hash
        occurred_at_override: Optional timestamp override
        
    Returns:
        Tuple of (ExpenseWriteResult, budget_sync_result)
    """
    # Create the expense
    result = create_expense(
        session=session,
        extracted=extracted,
        user_id=user.id,
        account_id=account_id,
        source_type=source_type,
        trip_id=trip_id,
        card_id=card_id,
        msg_id=msg_id,
        content_hash=content_hash,
        occurred_at_override=occurred_at_override,
    )
    
    # If new expense created, sync with budget
    budget_sync = None
    if result.created and user.current_budget_id:
        budget_sync = sync_expense_with_budget(
            session=session,
            expense=result.expense,
            user=user,
        )
    
    return result, budget_sync

