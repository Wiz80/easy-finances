"""
Budget storage operations for the Configuration Agent.

Handles budget creation, allocation management, and spending updates.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Budget, BudgetAllocation, BudgetFundingSource, Category, Trip, User

logger = get_logger(__name__)


# Category slug mapping for budget allocations
CATEGORY_MAPPING = {
    "category_food": "food",
    "category_lodging": "lodging",
    "category_transport": "transport",
    "category_tourism": "tourism",
    "category_gifts": "gifts",
    "category_contingency": "misc",  # Map contingency to misc/other
}


@dataclass
class BudgetWriteResult:
    """Result of a budget write operation."""
    success: bool
    budget_id: UUID | None = None
    budget: Budget | None = None
    error: str | None = None


def get_budget_by_id(db: Session, budget_id: UUID) -> Budget | None:
    """Get budget by ID with allocations and funding sources."""
    return db.query(Budget).filter(Budget.id == budget_id).first()


def get_user_budgets(
    db: Session,
    user_id: UUID,
    status: str | None = None,
    trip_id: UUID | None = None
) -> list[Budget]:
    """
    Get budgets for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        status: Optional status filter (active, completed, cancelled)
        trip_id: Optional trip filter
        
    Returns:
        List of Budget objects
    """
    query = db.query(Budget).filter(Budget.user_id == user_id)
    
    if status:
        query = query.filter(Budget.status == status)
    
    if trip_id:
        query = query.filter(Budget.trip_id == trip_id)
    
    return query.order_by(Budget.start_date.desc()).all()


def get_active_budget_for_trip(db: Session, trip_id: UUID) -> Budget | None:
    """Get the active budget for a trip."""
    return db.query(Budget).filter(
        Budget.trip_id == trip_id,
        Budget.status == "active"
    ).first()


def create_budget(
    db: Session,
    user_id: UUID,
    name: str,
    total_amount: Decimal,
    currency: str,
    start_date: date,
    end_date: date,
    trip_id: UUID | None = None,
    description: str | None = None,
    allocations: dict[str, Decimal] | None = None,
) -> BudgetWriteResult:
    """
    Create a new budget with optional allocations.
    
    Args:
        db: Database session
        user_id: User UUID
        name: Budget name
        total_amount: Total budget amount
        currency: Currency code (ISO 4217)
        start_date: Budget start date
        end_date: Budget end date
        trip_id: Optional trip to link
        description: Optional description
        allocations: Dict mapping category_key to amount
            e.g., {"category_food": Decimal("1500000"), "category_lodging": Decimal("2000000")}
        
    Returns:
        BudgetWriteResult with budget_id and budget object
    """
    try:
        # Create budget
        budget = Budget(
            user_id=user_id,
            trip_id=trip_id,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            total_amount=total_amount,
            currency=currency,
            status="active",
        )
        
        db.add(budget)
        db.flush()  # Get the ID
        
        # Create allocations if provided
        if allocations:
            _create_allocations(db, budget.id, currency, allocations)
        
        db.commit()
        db.refresh(budget)
        
        logger.info(
            "budget_created",
            budget_id=str(budget.id),
            user_id=str(user_id),
            total=str(total_amount),
            currency=currency,
            allocations=len(allocations) if allocations else 0
        )
        
        return BudgetWriteResult(
            success=True,
            budget_id=budget.id,
            budget=budget
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_budget_failed", user_id=str(user_id), error=str(e), exc_info=True)
        return BudgetWriteResult(success=False, error=str(e))


def create_budget_from_flow_data(
    db: Session,
    user_id: UUID,
    flow_data: dict[str, Any],
    trip_id: UUID | None = None,
) -> BudgetWriteResult:
    """
    Create budget from Configuration Agent flow data.
    
    Args:
        db: Database session
        user_id: User UUID
        flow_data: Flow data from conversation
            Expected keys: total_amount, category_food, category_lodging, etc.
        trip_id: Optional trip to link
        
    Returns:
        BudgetWriteResult
    """
    try:
        # Get user for currency
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return BudgetWriteResult(success=False, error="User not found")
        
        currency = user.home_currency
        
        # Parse total amount
        total_str = str(flow_data.get("total_amount", "0"))
        total_amount = _parse_decimal(total_str)
        
        # Determine dates
        if trip_id:
            trip = db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                start_date = trip.start_date
                end_date = trip.end_date or date.today()
                name = f"Presupuesto {trip.name}"
            else:
                start_date = date.today()
                end_date = date.today()
                name = "Nuevo Presupuesto"
        else:
            start_date = date.today()
            end_date = date.today()
            name = "Nuevo Presupuesto"
        
        # Extract allocations
        allocations = {}
        for key in CATEGORY_MAPPING.keys():
            if key in flow_data:
                amount_str = str(flow_data[key])
                amount = _parse_decimal(amount_str)
                if amount > 0:
                    allocations[key] = amount
        
        return create_budget(
            db=db,
            user_id=user_id,
            name=name,
            total_amount=total_amount,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
            trip_id=trip_id,
            allocations=allocations,
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_budget_from_flow_failed", error=str(e), exc_info=True)
        return BudgetWriteResult(success=False, error=str(e))


def _create_allocations(
    db: Session,
    budget_id: UUID,
    currency: str,
    allocations: dict[str, Decimal]
) -> list[BudgetAllocation]:
    """
    Create budget allocations for categories.
    
    Args:
        db: Database session
        budget_id: Budget UUID
        currency: Currency code
        allocations: Dict mapping category_key to amount
        
    Returns:
        List of created BudgetAllocation objects
    """
    created = []
    
    for key, amount in allocations.items():
        # Get category slug from mapping
        slug = CATEGORY_MAPPING.get(key, key.replace("category_", ""))
        
        # Find category by slug
        category = db.query(Category).filter(Category.slug == slug).first()
        
        if not category:
            logger.warning(f"Category not found for slug: {slug}")
            continue
        
        allocation = BudgetAllocation(
            budget_id=budget_id,
            category_id=category.id,
            allocated_amount=amount,
            currency=currency,
            spent_amount=Decimal("0"),
            alert_threshold_percent=80,
        )
        
        db.add(allocation)
        created.append(allocation)
    
    return created


def add_allocation(
    db: Session,
    budget_id: UUID,
    category_id: UUID,
    amount: Decimal,
    alert_threshold: int = 80
) -> BudgetAllocation | None:
    """
    Add an allocation to a budget.
    
    Args:
        db: Database session
        budget_id: Budget UUID
        category_id: Category UUID
        amount: Allocated amount
        alert_threshold: Alert percentage threshold
        
    Returns:
        BudgetAllocation or None on error
    """
    try:
        budget = get_budget_by_id(db, budget_id)
        if not budget:
            return None
        
        # Check if allocation already exists
        existing = db.query(BudgetAllocation).filter(
            BudgetAllocation.budget_id == budget_id,
            BudgetAllocation.category_id == category_id
        ).first()
        
        if existing:
            existing.allocated_amount = amount
            existing.alert_threshold_percent = alert_threshold
            existing.updated_at = datetime.utcnow()
            db.commit()
            return existing
        
        allocation = BudgetAllocation(
            budget_id=budget_id,
            category_id=category_id,
            allocated_amount=amount,
            currency=budget.currency,
            spent_amount=Decimal("0"),
            alert_threshold_percent=alert_threshold,
        )
        
        db.add(allocation)
        db.commit()
        db.refresh(allocation)
        
        return allocation
        
    except Exception as e:
        db.rollback()
        logger.error("add_allocation_failed", budget_id=str(budget_id), error=str(e))
        return None


def update_allocation_spent(
    db: Session,
    budget_id: UUID,
    category_id: UUID,
    amount_spent: Decimal
) -> bool:
    """
    Update the spent amount for a budget allocation.
    
    Called when expenses are logged to update tracking.
    
    Args:
        db: Database session
        budget_id: Budget UUID
        category_id: Category UUID
        amount_spent: Amount to add to spent
        
    Returns:
        True if updated successfully
    """
    try:
        allocation = db.query(BudgetAllocation).filter(
            BudgetAllocation.budget_id == budget_id,
            BudgetAllocation.category_id == category_id
        ).first()
        
        if not allocation:
            return False
        
        allocation.spent_amount += amount_spent
        allocation.updated_at = datetime.utcnow()
        
        # Check if we should send an alert
        if allocation.should_alert:
            logger.info(
                "budget_alert_triggered",
                budget_id=str(budget_id),
                category_id=str(category_id),
                percent_used=allocation.percent_used
            )
            # TODO: Send notification
            allocation.alert_sent = True
        
        db.commit()
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error("update_allocation_spent_failed", error=str(e))
        return False


def add_funding_source(
    db: Session,
    budget_id: UUID,
    source_type: str,
    account_id: UUID | None = None,
    card_id: UUID | None = None,
    cash_currency: str | None = None,
    cash_amount: Decimal | None = None,
    is_default: bool = False,
    priority: int = 1,
    notes: str | None = None,
) -> BudgetFundingSource | None:
    """
    Add a funding source to a budget.
    
    Args:
        db: Database session
        budget_id: Budget UUID
        source_type: "card", "account", or "cash"
        account_id: Account UUID (for account sources)
        card_id: Card UUID (for card sources)
        cash_currency: Currency for cash sources
        cash_amount: Amount for cash sources
        is_default: Whether this is the default source
        priority: Priority order (1 = highest)
        notes: Optional notes
        
    Returns:
        BudgetFundingSource or None on error
    """
    try:
        # If setting as default, unset other defaults
        if is_default:
            db.query(BudgetFundingSource).filter(
                BudgetFundingSource.budget_id == budget_id
            ).update({"is_default": False})
        
        source = BudgetFundingSource(
            budget_id=budget_id,
            source_type=source_type,
            account_id=account_id,
            card_id=card_id,
            cash_currency=cash_currency,
            cash_amount=cash_amount,
            is_default=is_default,
            priority=priority,
            notes=notes,
        )
        
        db.add(source)
        db.commit()
        db.refresh(source)
        
        logger.info(
            "funding_source_added",
            budget_id=str(budget_id),
            source_type=source_type
        )
        
        return source
        
    except Exception as e:
        db.rollback()
        logger.error("add_funding_source_failed", budget_id=str(budget_id), error=str(e))
        return None


def get_budget_summary(db: Session, budget_id: UUID) -> dict | None:
    """
    Get a summary of budget status.
    
    Args:
        db: Database session
        budget_id: Budget UUID
        
    Returns:
        Dict with budget summary or None
    """
    budget = get_budget_by_id(db, budget_id)
    if not budget:
        return None
    
    allocations_summary = []
    for alloc in budget.allocations:
        allocations_summary.append({
            "category": alloc.category.name if alloc.category else "Unknown",
            "allocated": float(alloc.allocated_amount),
            "spent": float(alloc.spent_amount),
            "remaining": float(alloc.remaining),
            "percent_used": alloc.percent_used,
        })
    
    return {
        "id": str(budget.id),
        "name": budget.name,
        "total_amount": float(budget.total_amount),
        "total_allocated": float(budget.total_allocated),
        "total_spent": float(budget.total_spent),
        "remaining": float(budget.remaining),
        "currency": budget.currency,
        "start_date": budget.start_date.isoformat(),
        "end_date": budget.end_date.isoformat(),
        "status": budget.status,
        "allocations": allocations_summary,
    }


def _parse_decimal(value: str) -> Decimal:
    """Parse a string into Decimal, handling various formats."""
    if not value:
        return Decimal("0")
    
    # Remove currency symbols and formatting
    cleaned = str(value).replace("$", "").replace(",", "").replace(" ", "").strip()
    
    # Keep only digits and decimal point
    result = ""
    for c in cleaned:
        if c.isdigit() or c == ".":
            result += c
    
    try:
        return Decimal(result) if result else Decimal("0")
    except Exception:
        return Decimal("0")

