"""
Context loading node for Configuration Agent.

Loads user data and conversation state from the database.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agents.configuration_agent.state import ConfigurationAgentState
from app.config import settings
from app.logging_config import get_logger
from app.models import ConversationState, User

logger = get_logger(__name__)


def load_context_node(
    state: ConfigurationAgentState,
    *,
    db: Session,
) -> ConfigurationAgentState:
    """
    Load user and conversation context from the database.
    
    This node:
    1. Fetches user data (name, currency, timezone, onboarding status)
    2. Loads active conversation state (if any)
    3. Populates state with context for subsequent nodes
    
    Args:
        state: Current agent state
        db: Database session (injected)
        
    Returns:
        Updated state with user and conversation context
    """
    user_id = state["user_id"]
    
    logger.debug(
        "load_context_start",
        request_id=state.get("request_id"),
        user_id=str(user_id)
    )
    
    try:
        # Load user from database
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.error("user_not_found", user_id=str(user_id))
            return {
                **state,
                "status": "error",
                "errors": state.get("errors", []) + ["Usuario no encontrado"],
            }
        
        # Update state with user context
        state = {
            **state,
            "user_name": user.nickname or user.full_name,
            "home_currency": user.home_currency,
            "timezone": user.timezone,
            "onboarding_completed": user.onboarding_status == "completed",
        }
        
        # Load active conversation (if any)
        conversation = db.query(ConversationState).filter(
            ConversationState.user_id == user_id,
            ConversationState.status == "active"
        ).first()
        
        if conversation:
            # Check if expired
            if conversation.is_expired:
                conversation.status = "expired"
                db.commit()
                logger.info(
                    "conversation_expired",
                    conversation_id=str(conversation.id)
                )
            else:
                # Load conversation context
                state = {
                    **state,
                    "conversation_id": conversation.id,
                    "current_flow": conversation.current_flow,
                    "flow_data": conversation.state_data or {},
                    "pending_field": conversation.pending_confirmation,
                }
                logger.debug(
                    "conversation_loaded",
                    conversation_id=str(conversation.id),
                    flow=conversation.current_flow,
                    step=conversation.current_step
                )
        
        # If no active conversation and user needs onboarding
        if not state.get("conversation_id") and not state.get("onboarding_completed"):
            state["current_flow"] = "onboarding"
        elif not state.get("conversation_id"):
            state["current_flow"] = "general"
        
        logger.debug(
            "load_context_complete",
            request_id=state.get("request_id"),
            current_flow=state.get("current_flow"),
            onboarding_completed=state.get("onboarding_completed")
        )
        
        return state
        
    except Exception as e:
        logger.error(
            "load_context_error",
            request_id=state.get("request_id"),
            error=str(e),
            exc_info=True
        )
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Error cargando contexto: {str(e)}"],
        }


def create_or_update_conversation(
    db: Session,
    user_id,
    flow: str,
    step: str,
    state_data: dict | None = None,
    pending_field: str | None = None,
) -> ConversationState:
    """
    Create a new conversation or update existing one.
    
    Args:
        db: Database session
        user_id: User UUID
        flow: Conversation flow type
        step: Current step in flow
        state_data: Accumulated data
        pending_field: Field we're waiting for
        
    Returns:
        ConversationState instance
    """
    # Expire any existing active conversations
    db.query(ConversationState).filter(
        ConversationState.user_id == user_id,
        ConversationState.status == "active"
    ).update({"status": "expired"})
    
    # Create new conversation
    now = datetime.utcnow()
    conversation = ConversationState(
        user_id=user_id,
        current_flow=flow,
        current_step=step,
        state_data=state_data or {},
        pending_confirmation=pending_field,
        session_started_at=now,
        last_interaction_at=now,
        expires_at=now + timedelta(minutes=settings.conversation_timeout_minutes),
        status="active",
        message_count=0,
        message_history=[]
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
    
    return conversation

