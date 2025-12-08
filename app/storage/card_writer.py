"""
Card storage operations for the Configuration Agent.

Handles card and account creation for budget funding sources.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Account, Card, User

logger = get_logger(__name__)


@dataclass
class CardWriteResult:
    """Result of a card write operation."""
    success: bool
    card_id: UUID | None = None
    card: Card | None = None
    error: str | None = None


@dataclass
class AccountWriteResult:
    """Result of an account write operation."""
    success: bool
    account_id: UUID | None = None
    account: Account | None = None
    error: str | None = None


def get_card_by_id(db: Session, card_id: UUID) -> Card | None:
    """Get card by ID."""
    return db.query(Card).filter(Card.id == card_id).first()


def get_account_by_id(db: Session, account_id: UUID) -> Account | None:
    """Get account by ID."""
    return db.query(Account).filter(Account.id == account_id).first()


def get_user_cards(db: Session, user_id: UUID, active_only: bool = True) -> list[Card]:
    """
    Get all cards for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        active_only: Only return active cards
        
    Returns:
        List of Card objects
    """
    # Get user's accounts first
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    account_ids = [a.id for a in accounts]
    
    if not account_ids:
        return []
    
    query = db.query(Card).filter(Card.account_id.in_(account_ids))
    
    if active_only:
        query = query.filter(Card.is_active == True)
    
    return query.order_by(Card.is_default.desc(), Card.name).all()


def get_user_accounts(db: Session, user_id: UUID, active_only: bool = True) -> list[Account]:
    """
    Get all accounts for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        active_only: Only return active accounts
        
    Returns:
        List of Account objects
    """
    query = db.query(Account).filter(Account.user_id == user_id)
    
    if active_only:
        query = query.filter(Account.is_active == True)
    
    return query.order_by(Account.is_default.desc(), Account.name).all()


def get_default_account(db: Session, user_id: UUID) -> Account | None:
    """Get the default account for a user."""
    return db.query(Account).filter(
        Account.user_id == user_id,
        Account.is_default == True,
        Account.is_active == True
    ).first()


def get_default_card(db: Session, user_id: UUID) -> Card | None:
    """Get the default card for a user."""
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    account_ids = [a.id for a in accounts]
    
    if not account_ids:
        return None
    
    return db.query(Card).filter(
        Card.account_id.in_(account_ids),
        Card.is_default == True,
        Card.is_active == True
    ).first()


def create_account(
    db: Session,
    user_id: UUID,
    name: str,
    account_type: str,
    currency: str,
    institution: str | None = None,
    last_four_digits: str | None = None,
    is_default: bool = False,
) -> AccountWriteResult:
    """
    Create a new account.
    
    Args:
        db: Database session
        user_id: User UUID
        name: Account name (e.g., "Bancolombia Savings")
        account_type: Type (checking, savings, cash, credit)
        currency: Currency code (ISO 4217)
        institution: Bank/institution name
        last_four_digits: Last 4 digits of account number
        is_default: Whether this is the default account
        
    Returns:
        AccountWriteResult
    """
    try:
        # If setting as default, unset other defaults
        if is_default:
            db.query(Account).filter(
                Account.user_id == user_id
            ).update({"is_default": False})
        
        account = Account(
            user_id=user_id,
            name=name,
            account_type=account_type,
            currency=currency,
            institution=institution,
            last_four_digits=last_four_digits,
            is_active=True,
            is_default=is_default,
        )
        
        db.add(account)
        db.commit()
        db.refresh(account)
        
        logger.info(
            "account_created",
            account_id=str(account.id),
            user_id=str(user_id),
            name=name,
            type=account_type
        )
        
        return AccountWriteResult(
            success=True,
            account_id=account.id,
            account=account
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_account_failed", user_id=str(user_id), error=str(e))
        return AccountWriteResult(success=False, error=str(e))


def create_card(
    db: Session,
    account_id: UUID,
    name: str,
    card_type: str,
    network: str,
    last_four_digits: str,
    issuer: str | None = None,
    color: str | None = None,
    is_default: bool = False,
) -> CardWriteResult:
    """
    Create a new card linked to an account.
    
    Args:
        db: Database session
        account_id: Account UUID
        name: Card name (e.g., "Visa Travel")
        card_type: Type (credit, debit)
        network: Network (visa, mastercard, amex)
        last_four_digits: Last 4 digits
        issuer: Card issuer/bank
        color: Card color for UI
        is_default: Whether this is the default card
        
    Returns:
        CardWriteResult
    """
    try:
        account = get_account_by_id(db, account_id)
        if not account:
            return CardWriteResult(success=False, error="Account not found")
        
        # If setting as default, unset other defaults for this user's cards
        if is_default:
            user_accounts = db.query(Account).filter(
                Account.user_id == account.user_id
            ).all()
            account_ids = [a.id for a in user_accounts]
            
            db.query(Card).filter(
                Card.account_id.in_(account_ids)
            ).update({"is_default": False})
        
        card = Card(
            account_id=account_id,
            name=name,
            card_type=card_type.lower(),
            network=network.lower(),
            last_four_digits=last_four_digits,
            issuer=issuer,
            color=color,
            is_active=True,
            is_default=is_default,
        )
        
        db.add(card)
        db.commit()
        db.refresh(card)
        
        logger.info(
            "card_created",
            card_id=str(card.id),
            account_id=str(account_id),
            name=name,
            network=network
        )
        
        return CardWriteResult(
            success=True,
            card_id=card.id,
            card=card
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_card_failed", account_id=str(account_id), error=str(e))
        return CardWriteResult(success=False, error=str(e))


def create_card_for_user(
    db: Session,
    user_id: UUID,
    name: str,
    card_type: str,
    network: str,
    last_four_digits: str,
    issuer: str | None = None,
    is_default: bool = False,
) -> CardWriteResult:
    """
    Create a card for a user, automatically creating an account if needed.
    
    This is a convenience function for the Configuration Agent that
    creates both the account and card in one operation.
    
    Args:
        db: Database session
        user_id: User UUID
        name: Card name (e.g., "Visa Travel")
        card_type: Type (credit, debit)
        network: Network (visa, mastercard, amex)
        last_four_digits: Last 4 digits
        issuer: Card issuer/bank
        is_default: Whether this is the default card
        
    Returns:
        CardWriteResult
    """
    try:
        # Get user for currency
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return CardWriteResult(success=False, error="User not found")
        
        # Find or create an account for this card
        # Look for an existing account from the same issuer
        account = None
        if issuer:
            account = db.query(Account).filter(
                Account.user_id == user_id,
                Account.institution == issuer,
                Account.is_active == True
            ).first()
        
        if not account:
            # Create a new account for this card
            account_type = "credit" if card_type.lower() == "credit" else "checking"
            account_result = create_account(
                db=db,
                user_id=user_id,
                name=f"Cuenta {issuer or network.title()}",
                account_type=account_type,
                currency=user.home_currency,
                institution=issuer,
                is_default=False,
            )
            
            if not account_result.success:
                return CardWriteResult(success=False, error=account_result.error)
            
            account = account_result.account
        
        # Create the card
        return create_card(
            db=db,
            account_id=account.id,
            name=name,
            card_type=card_type,
            network=network,
            last_four_digits=last_four_digits,
            issuer=issuer,
            is_default=is_default,
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_card_for_user_failed", user_id=str(user_id), error=str(e))
        return CardWriteResult(success=False, error=str(e))


def create_card_from_flow_data(
    db: Session,
    user_id: UUID,
    flow_data: dict[str, Any],
) -> CardWriteResult:
    """
    Create card from Configuration Agent flow data.
    
    Args:
        db: Database session
        user_id: User UUID
        flow_data: Flow data from conversation
            Expected keys: card_type, network, last_four, issuer, name
            
    Returns:
        CardWriteResult
    """
    try:
        card_type = flow_data.get("card_type", "credit")
        network = flow_data.get("network", "visa")
        last_four = flow_data.get("last_four", "0000")
        issuer = flow_data.get("issuer")
        name = flow_data.get("name", f"{network.title()} {card_type.title()}")
        is_default = flow_data.get("is_default", False)
        
        return create_card_for_user(
            db=db,
            user_id=user_id,
            name=name,
            card_type=card_type,
            network=network,
            last_four_digits=last_four,
            issuer=issuer,
            is_default=is_default,
        )
        
    except Exception as e:
        logger.error("create_card_from_flow_failed", error=str(e))
        return CardWriteResult(success=False, error=str(e))


def update_card(
    db: Session,
    card_id: UUID,
    **updates: Any
) -> CardWriteResult:
    """
    Update card fields.
    
    Args:
        db: Database session
        card_id: Card UUID
        **updates: Fields to update
        
    Returns:
        CardWriteResult
    """
    try:
        card = get_card_by_id(db, card_id)
        if not card:
            return CardWriteResult(success=False, error="Card not found")
        
        allowed_fields = {
            "name", "card_type", "network", "last_four_digits",
            "issuer", "color", "is_active", "is_default"
        }
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(card, field):
                setattr(card, field, value)
        
        card.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(card)
        
        return CardWriteResult(success=True, card_id=card_id, card=card)
        
    except Exception as e:
        db.rollback()
        logger.error("update_card_failed", card_id=str(card_id), error=str(e))
        return CardWriteResult(success=False, error=str(e))


def deactivate_card(db: Session, card_id: UUID) -> CardWriteResult:
    """Deactivate a card."""
    return update_card(db, card_id, is_active=False)


def set_default_card(db: Session, user_id: UUID, card_id: UUID) -> CardWriteResult:
    """
    Set a card as the default for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        card_id: Card UUID to set as default
        
    Returns:
        CardWriteResult
    """
    try:
        # Verify card belongs to user
        card = get_card_by_id(db, card_id)
        if not card:
            return CardWriteResult(success=False, error="Card not found")
        
        account = get_account_by_id(db, card.account_id)
        if not account or account.user_id != user_id:
            return CardWriteResult(success=False, error="Card does not belong to user")
        
        # Unset other defaults
        user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
        account_ids = [a.id for a in user_accounts]
        
        db.query(Card).filter(
            Card.account_id.in_(account_ids)
        ).update({"is_default": False})
        
        # Set this card as default
        card.is_default = True
        card.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(card)
        
        logger.info("default_card_set", card_id=str(card_id), user_id=str(user_id))
        
        return CardWriteResult(success=True, card_id=card_id, card=card)
        
    except Exception as e:
        db.rollback()
        logger.error("set_default_card_failed", error=str(e))
        return CardWriteResult(success=False, error=str(e))

