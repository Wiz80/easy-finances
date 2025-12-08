"""
Persistence node for Configuration Agent.

Handles saving changes to the database based on flow completion.
Uses the storage layer writers for all database operations.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agents.configuration_agent.state import ConfigurationAgentState
from app.config import settings
from app.logging_config import get_logger
from app.models import ConversationState, User
from app.storage import (
    # User operations
    update_user,
    complete_onboarding,
    activate_travel_mode,
    # Trip operations
    create_trip as storage_create_trip,
    get_country_info,
    # Budget operations
    create_budget_from_flow_data,
    # Card operations
    create_card_from_flow_data,
    # Conversation operations
    create_conversation,
    update_conversation,
)

logger = get_logger(__name__)


def persist_changes_node(
    state: ConfigurationAgentState,
    *,
    db: Session,
) -> ConfigurationAgentState:
    """
    Persist changes to the database.
    
    This node:
    1. Checks if persistence is needed
    2. Routes to appropriate persistence handler
    3. Updates conversation state
    
    Args:
        state: Current agent state
        db: Database session (injected)
        
    Returns:
        Updated state with persistence results
    """
    if not state.get("should_persist"):
        # Still need to update conversation state
        return _update_conversation_state(state, db)
    
    persist_type = state.get("persist_type")
    persist_data = state.get("persist_data", {})
    
    logger.debug(
        "persist_changes_start",
        request_id=state.get("request_id"),
        persist_type=persist_type
    )
    
    try:
        if persist_type == "user_update":
            _persist_user_update(state, db, persist_data)
        elif persist_type == "user_complete_onboarding":
            _persist_user_complete_onboarding(state, db, persist_data)
        elif persist_type == "trip_create":
            _persist_trip_create(state, db, persist_data)
        elif persist_type == "budget_create":
            _persist_budget_create(state, db, persist_data)
        elif persist_type == "card_create":
            _persist_card_create(state, db, persist_data)
        
        logger.info(
            "persist_changes_success",
            request_id=state.get("request_id"),
            persist_type=persist_type
        )
        
    except Exception as e:
        logger.error(
            "persist_changes_error",
            request_id=state.get("request_id"),
            persist_type=persist_type,
            error=str(e),
            exc_info=True
        )
        state = {
            **state,
            "errors": state.get("errors", []) + [f"Error guardando datos: {str(e)}"],
        }
    
    # Update conversation state
    return _update_conversation_state(state, db)


def _persist_user_update(
    state: ConfigurationAgentState,
    db: Session,
    data: dict
) -> None:
    """Update user fields using storage layer."""
    user_id = state["user_id"]
    
    result = update_user(db, user_id, **data)
    
    if not result.success:
        raise ValueError(f"Failed to update user: {result.error}")


def _persist_user_complete_onboarding(
    state: ConfigurationAgentState,
    db: Session,
    data: dict
) -> None:
    """Complete user onboarding using storage layer."""
    user_id = state["user_id"]
    flow_data = state.get("flow_data", {})
    
    result = complete_onboarding(
        db=db,
        user_id=user_id,
        full_name=flow_data.get("name"),
        nickname=flow_data.get("name", "").split()[0] if flow_data.get("name") else None,
        home_currency=flow_data.get("currency"),
        timezone=data.get("timezone") or flow_data.get("timezone"),
    )
    
    if not result.success:
        raise ValueError(f"Failed to complete onboarding: {result.error}")


def _persist_trip_create(
    state: ConfigurationAgentState,
    db: Session,
    data: dict
) -> None:
    """Create a new trip using storage layer."""
    user_id = state["user_id"]
    
    # Parse dates
    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))
    
    # Get country info for currency and timezone
    country = data.get("country", "XX")[:2].upper()
    country_info = get_country_info(country)
    
    result = storage_create_trip(
        db=db,
        user_id=user_id,
        name=data.get("name", "Nuevo Viaje"),
        start_date=start_date or datetime.utcnow().date(),
        end_date=end_date,
        destination_country=country,
        destination_city=data.get("city"),
        local_currency=data.get("currency") or country_info["currency"],
        timezone=state.get("timezone") or country_info["timezone"],
        set_as_current=True,
    )
    
    if not result.success:
        raise ValueError(f"Failed to create trip: {result.error}")


def _persist_budget_create(
    state: ConfigurationAgentState,
    db: Session,
    data: dict
) -> None:
    """Create a new budget using storage layer."""
    user_id = state["user_id"]
    
    # Get current trip if in travel mode
    user = db.query(User).filter(User.id == user_id).first()
    trip_id = user.current_trip_id if user and user.travel_mode_active else None
    
    result = create_budget_from_flow_data(
        db=db,
        user_id=user_id,
        flow_data=data,
        trip_id=trip_id,
    )
    
    if not result.success:
        raise ValueError(f"Failed to create budget: {result.error}")
    
    logger.info(
        "budget_created_from_flow",
        budget_id=str(result.budget_id),
        user_id=str(user_id),
        trip_id=str(trip_id) if trip_id else None
    )


def _persist_card_create(
    state: ConfigurationAgentState,
    db: Session,
    data: dict
) -> None:
    """Create a new card using storage layer."""
    user_id = state["user_id"]
    
    result = create_card_from_flow_data(
        db=db,
        user_id=user_id,
        flow_data=data,
    )
    
    if not result.success:
        raise ValueError(f"Failed to create card: {result.error}")
    
    logger.info(
        "card_created_from_flow",
        card_id=str(result.card_id),
        user_id=str(user_id)
    )


def _update_conversation_state(
    state: ConfigurationAgentState,
    db: Session
) -> ConfigurationAgentState:
    """Update or create conversation state using storage layer."""
    user_id = state["user_id"]
    conversation_id = state.get("conversation_id")
    current_flow = state.get("current_flow", "general")
    pending_field = state.get("pending_field")
    flow_data = state.get("flow_data", {})
    
    if conversation_id:
        # Update existing conversation
        result = update_conversation(
            db=db,
            conversation_id=conversation_id,
            flow=current_flow,
            step=pending_field or "idle",
            state_data=flow_data,
            pending_confirmation=pending_field,
            user_message=state.get("message_body"),
            bot_message=state.get("response_text"),
        )
        
        # If flow is done, complete the conversation
        if result.success and current_flow == "general" and not pending_field:
            from app.storage import complete_conversation
            complete_conversation(db, conversation_id)
    else:
        # Create new conversation if we have an active flow
        if current_flow != "general" or pending_field:
            result = create_conversation(
                db=db,
                user_id=user_id,
                flow=current_flow,
                step=pending_field or "idle",
                state_data=flow_data,
            )
            
            if result.success and result.conversation:
                # Add messages
                if state.get("message_body"):
                    result.conversation.add_message("user", state["message_body"])
                if state.get("response_text"):
                    result.conversation.add_message("bot", state["response_text"])
                db.commit()
                
                state = {**state, "conversation_id": result.conversation_id}
    
    return {
        **state,
        "status": "completed" if state.get("response_text") else "error",
    }


def _parse_date(date_str: str | None):
    """Parse a date string into a date object."""
    if not date_str:
        return None
    
    from datetime import datetime
    
    # Try various formats
    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    
    return None

