"""
Conversation state management for the Configuration Agent.

Handles conversation state CRUD and session management.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.logging_config import get_logger
from app.models import ConversationState

logger = get_logger(__name__)


@dataclass
class ConversationResult:
    """Result of a conversation operation."""
    success: bool
    conversation_id: UUID | None = None
    conversation: ConversationState | None = None
    error: str | None = None


def get_conversation_by_id(db: Session, conversation_id: UUID) -> ConversationState | None:
    """Get conversation by ID."""
    return db.query(ConversationState).filter(
        ConversationState.id == conversation_id
    ).first()


def get_active_conversation(db: Session, user_id: UUID) -> ConversationState | None:
    """
    Get the active conversation for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Active ConversationState or None
    """
    conversation = db.query(ConversationState).filter(
        ConversationState.user_id == user_id,
        ConversationState.status == "active"
    ).first()
    
    # Check if expired
    if conversation and conversation.is_expired:
        conversation.expire()
        db.commit()
        return None
    
    return conversation


def get_user_conversations(
    db: Session,
    user_id: UUID,
    status: str | None = None,
    limit: int = 10
) -> list[ConversationState]:
    """
    Get conversations for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        status: Optional status filter
        limit: Maximum number to return
        
    Returns:
        List of ConversationState objects
    """
    query = db.query(ConversationState).filter(
        ConversationState.user_id == user_id
    )
    
    if status:
        query = query.filter(ConversationState.status == status)
    
    return query.order_by(
        ConversationState.last_interaction_at.desc()
    ).limit(limit).all()


def create_conversation(
    db: Session,
    user_id: UUID,
    flow: str,
    step: str,
    state_data: dict[str, Any] | None = None,
    timeout_minutes: int | None = None,
) -> ConversationResult:
    """
    Create a new conversation, expiring any existing active ones.
    
    Args:
        db: Database session
        user_id: User UUID
        flow: Initial flow (onboarding, trip_setup, budget_config, etc.)
        step: Initial step within the flow
        state_data: Initial state data
        timeout_minutes: Custom timeout (uses config default if not provided)
        
    Returns:
        ConversationResult with conversation_id and conversation object
    """
    try:
        # Expire any existing active conversations
        db.query(ConversationState).filter(
            ConversationState.user_id == user_id,
            ConversationState.status == "active"
        ).update({"status": "expired"})
        
        timeout = timeout_minutes or settings.conversation_timeout_minutes
        now = datetime.utcnow()
        
        conversation = ConversationState(
            user_id=user_id,
            current_flow=flow,
            current_step=step,
            state_data=state_data or {},
            session_started_at=now,
            last_interaction_at=now,
            expires_at=now + timedelta(minutes=timeout),
            status="active",
            message_count=0,
            message_history=[],
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        logger.info(
            "conversation_created",
            conversation_id=str(conversation.id),
            user_id=str(user_id),
            flow=flow,
            step=step
        )
        
        return ConversationResult(
            success=True,
            conversation_id=conversation.id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("create_conversation_failed", user_id=str(user_id), error=str(e))
        return ConversationResult(success=False, error=str(e))


def update_conversation(
    db: Session,
    conversation_id: UUID,
    flow: str | None = None,
    step: str | None = None,
    state_data: dict[str, Any] | None = None,
    pending_confirmation: str | None = None,
    pending_entity_type: str | None = None,
    pending_entity_data: dict | None = None,
    user_message: str | None = None,
    bot_message: str | None = None,
) -> ConversationResult:
    """
    Update a conversation's state.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        flow: New flow (if changing)
        step: New step (if changing)
        state_data: Updated state data (merged with existing)
        pending_confirmation: What we're waiting for
        pending_entity_type: Type of entity being confirmed
        pending_entity_data: Entity data awaiting confirmation
        user_message: User's message to add to history
        bot_message: Bot's response to add to history
        
    Returns:
        ConversationResult
    """
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        # Update flow and step
        if flow is not None:
            conversation.current_flow = flow
        if step is not None:
            conversation.current_step = step
        
        # Merge state data
        if state_data is not None:
            if conversation.state_data is None:
                conversation.state_data = {}
            conversation.state_data.update(state_data)
            flag_modified(conversation, "state_data")  # Mark JSONB as modified
        
        # Update pending confirmation
        conversation.pending_confirmation = pending_confirmation
        conversation.pending_entity_type = pending_entity_type
        conversation.pending_entity_data = pending_entity_data
        
        # Add messages to history
        if user_message:
            conversation.add_message("user", user_message)
        if bot_message:
            conversation.add_message("bot", bot_message)
        
        # Touch to extend expiration
        conversation.touch(settings.conversation_timeout_minutes)
        
        db.commit()
        db.refresh(conversation)
        
        logger.debug(
            "conversation_updated",
            conversation_id=str(conversation_id),
            flow=conversation.current_flow,
            step=conversation.current_step
        )
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("update_conversation_failed", conversation_id=str(conversation_id), error=str(e))
        return ConversationResult(success=False, error=str(e))


def update_conversation_state_data(
    db: Session,
    conversation_id: UUID,
    **data: Any
) -> ConversationResult:
    """
    Update specific fields in conversation state_data.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        **data: Key-value pairs to update in state_data
        
    Returns:
        ConversationResult
    """
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.update_state(**data)
        flag_modified(conversation, "state_data")  # Mark JSONB as modified
        conversation.touch(settings.conversation_timeout_minutes)
        
        db.commit()
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("update_state_data_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def set_pending_confirmation(
    db: Session,
    conversation_id: UUID,
    confirmation: str,
    entity_type: str,
    entity_data: dict,
) -> ConversationResult:
    """
    Set pending confirmation data.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        confirmation: Description of what needs confirmation
        entity_type: Type of entity (trip, budget, card, expense)
        entity_data: Data to persist after confirmation
        
    Returns:
        ConversationResult
    """
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.set_pending(confirmation, entity_type, entity_data)
        conversation.touch(settings.conversation_timeout_minutes)
        
        db.commit()
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("set_pending_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def clear_pending_confirmation(db: Session, conversation_id: UUID) -> ConversationResult:
    """Clear pending confirmation data."""
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.clear_pending()
        db.commit()
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("clear_pending_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def complete_conversation(db: Session, conversation_id: UUID) -> ConversationResult:
    """Mark a conversation as completed."""
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.complete()
        db.commit()
        
        logger.info("conversation_completed", conversation_id=str(conversation_id))
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("complete_conversation_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def cancel_conversation(db: Session, conversation_id: UUID) -> ConversationResult:
    """Cancel a conversation."""
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.cancel()
        db.commit()
        
        logger.info("conversation_cancelled", conversation_id=str(conversation_id))
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("cancel_conversation_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def expire_conversation(db: Session, conversation_id: UUID) -> ConversationResult:
    """Mark a conversation as expired."""
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if not conversation:
            return ConversationResult(success=False, error="Conversation not found")
        
        conversation.expire()
        db.commit()
        
        logger.info("conversation_expired", conversation_id=str(conversation_id))
        
        return ConversationResult(
            success=True,
            conversation_id=conversation_id,
            conversation=conversation
        )
        
    except Exception as e:
        db.rollback()
        logger.error("expire_conversation_failed", error=str(e))
        return ConversationResult(success=False, error=str(e))


def cleanup_expired_conversations(db: Session) -> int:
    """
    Clean up expired conversations.
    
    This should be called periodically to mark expired conversations.
    
    Args:
        db: Database session
        
    Returns:
        Number of conversations expired
    """
    try:
        now = datetime.utcnow()
        
        result = db.query(ConversationState).filter(
            ConversationState.status == "active",
            ConversationState.expires_at < now
        ).update({"status": "expired"})
        
        db.commit()
        
        if result > 0:
            logger.info("conversations_expired", count=result)
        
        return result
        
    except Exception as e:
        db.rollback()
        logger.error("cleanup_expired_failed", error=str(e))
        return 0


def get_conversation_summary(db: Session, conversation_id: UUID) -> dict | None:
    """
    Get a summary of a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        
    Returns:
        Dict with conversation summary or None
    """
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        return None
    
    return {
        "id": str(conversation.id),
        "user_id": str(conversation.user_id),
        "flow": conversation.current_flow,
        "step": conversation.current_step,
        "status": conversation.status,
        "state_data": conversation.state_data,
        "pending_confirmation": conversation.pending_confirmation,
        "message_count": conversation.message_count,
        "started_at": conversation.session_started_at.isoformat(),
        "last_interaction": conversation.last_interaction_at.isoformat(),
        "expires_at": conversation.expires_at.isoformat(),
        "is_active": conversation.is_active,
        "is_expired": conversation.is_expired,
    }

