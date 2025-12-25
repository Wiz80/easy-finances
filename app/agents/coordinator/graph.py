"""
Coordinator Agent Graph Definition.

Defines the LangGraph that orchestrates multi-agent routing:
1. Load context (user, conversation)
2. Check agent lock (sticky session)
3. Detect intent (if not locked)
4. Route to agent
5. Process response (handle handoffs)
6. Update state
"""

from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.common.intents import AgentType
from app.agents.coordinator.state import CoordinatorState
from app.logging_config import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Conditional Edge Functions
# ─────────────────────────────────────────────────────────────────────────────

def should_detect_intent(state: CoordinatorState) -> Literal["locked", "unlocked", "onboarding", "command"]:
    """
    Determine if we need to detect intent or use locked agent.
    
    Returns:
        - "locked": Session is locked to an agent
        - "unlocked": Need to detect intent
        - "onboarding": Force to configuration for onboarding
        - "command": Handle coordinator command
    """
    # Check for commands first
    if state.get("is_command"):
        return "command"
    
    # Check if onboarding is required
    if not state.get("onboarding_completed", False):
        return "onboarding"
    
    # Check for agent lock
    if state.get("agent_locked") and state.get("active_agent"):
        return "locked"
    
    return "unlocked"


def should_continue_or_handoff(state: CoordinatorState) -> Literal["done", "handoff"]:
    """
    Determine if we're done or need to handle a handoff.
    
    Returns:
        - "done": Finished processing
        - "handoff": Need to route to another agent
    """
    response = state.get("agent_response")
    handoff_count = state.get("handoff_count", 0)
    
    # Check for handoff request
    if response and response.wants_handoff:
        # Prevent infinite loops
        if handoff_count < 3:
            target = response.handoff_to
            # Only handoff to actual agents, not coordinator
            if target and target not in ("coordinator", "unknown"):
                return "handoff"
    
    return "done"


# ─────────────────────────────────────────────────────────────────────────────
# Node Functions
# ─────────────────────────────────────────────────────────────────────────────

async def load_context_node(state: CoordinatorState) -> CoordinatorState:
    """
    Load user and conversation context.
    
    This node:
    1. First tries to load conversation from Azure Blob cache (fast path)
    2. Falls back to database for user/conversation data
    3. Loads active trip and account info
    """
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.models import User, ConversationState, Trip
    from app.storage.user_writer import get_user_by_phone, create_user
    from app.storage.conversation_manager import get_active_conversation
    from app.config import settings
    
    request_id = state.get("request_id", "unknown")
    phone_number = state["phone_number"]
    profile_name = state.get("profile_name")
    
    logger.debug("load_context_start", request_id=request_id)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Try Azure Blob Cache first (fast path)
    # ─────────────────────────────────────────────────────────────────────────
    cached_conversation = None
    if settings.azure_storage_configured:
        try:
            from app.storage.conversation_cache import conversation_cache
            cached_conversation = await conversation_cache.get(phone_number)
            
            if cached_conversation:
                logger.debug(
                    "load_context_cache_hit",
                    request_id=request_id,
                    flow=cached_conversation.current_flow,
                    step=cached_conversation.pending_field,
                )
        except Exception as e:
            logger.warning("load_context_cache_error", error=str(e))
            # Continue with DB fallback
    
    # ─────────────────────────────────────────────────────────────────────────
    # Load user from database (always needed for persistent data)
    # ─────────────────────────────────────────────────────────────────────────
    db: Session = SessionLocal()
    try:
        # Get or create user
        user = get_user_by_phone(db, phone_number)
        if not user:
            # Create new user
            result = create_user(
                db=db,
                phone_number=phone_number,
                full_name=profile_name or "Usuario",
                nickname=profile_name,
            )
            if result.success and result.user_id:
                user = db.query(User).filter(User.id == result.user_id).first()
        
        if not user:
            logger.error("load_context_no_user", request_id=request_id)
            state["status"] = "error"
            state["errors"] = ["Could not create or find user"]
            state["response_text"] = "⚠️ Error al procesar tu solicitud. Por favor intenta de nuevo."
            return state
        
        # Check for active trip
        active_trip = None
        has_active_trip = False
        if user.current_trip_id:
            active_trip = db.query(Trip).filter(Trip.id == user.current_trip_id).first()
            has_active_trip = active_trip is not None
        
        # Get default account
        default_account_id = None
        if user.accounts:
            for account in user.accounts:
                if account.is_active:
                    default_account_id = account.id
                    break
        
        # ─────────────────────────────────────────────────────────────────────
        # Populate state - Use cache if available, otherwise DB
        # ─────────────────────────────────────────────────────────────────────
        
        # User data (always from DB - source of truth)
        state["user_id"] = user.id
        state["user_name"] = user.nickname or user.full_name
        state["home_currency"] = user.home_currency
        state["timezone"] = user.timezone
        state["onboarding_completed"] = user.onboarding_status == "completed"
        state["has_active_trip"] = has_active_trip
        state["active_trip_id"] = user.current_trip_id
        state["default_account_id"] = default_account_id
        
        # Conversation context - from cache if available
        if cached_conversation and not cached_conversation.is_expired():
            # Use cached conversation state
            state["active_agent"] = cached_conversation.active_agent
            state["agent_locked"] = cached_conversation.agent_locked
            state["lock_reason"] = cached_conversation.lock_reason
            state["current_flow"] = cached_conversation.current_flow
            # Use current_step from cache, fall back to pending_field
            state["current_step"] = cached_conversation.current_step or cached_conversation.pending_field
            state["pending_field"] = cached_conversation.pending_field
            state["flow_data"] = cached_conversation.flow_data or {}
            state["last_bot_message"] = cached_conversation.last_bot_message
            state["cache_loaded"] = True
            
            # Load conversation_id from cache if available
            if cached_conversation.conversation_id:
                from uuid import UUID
                try:
                    state["conversation_id"] = UUID(cached_conversation.conversation_id)
                except (ValueError, TypeError):
                    pass  # Invalid UUID in cache, will load from DB
            
            logger.debug(
                "load_context_from_cache",
                request_id=request_id,
                flow=cached_conversation.current_flow,
                current_step=cached_conversation.current_step,
                pending_field=cached_conversation.pending_field,
                conversation_id=cached_conversation.conversation_id,
            )
        else:
            # Fall back to DB conversation
            conversation = get_active_conversation(db, user.id)
            
            if conversation:
                state["conversation_id"] = conversation.id
                state["active_agent"] = conversation.active_agent
                state["agent_locked"] = conversation.agent_locked
                state["lock_reason"] = conversation.lock_reason
                state["current_flow"] = conversation.current_flow
                state["current_step"] = conversation.current_step
                state["pending_field"] = conversation.current_step  # Map step to pending_field
                state["flow_data"] = conversation.state_data or {}
                state["handoff_context"] = conversation.handoff_context
                state["last_bot_message"] = conversation.last_bot_message
            else:
                state["conversation_id"] = None
                state["active_agent"] = None
                state["agent_locked"] = False
                state["current_flow"] = "unknown"
                state["pending_field"] = None
                state["flow_data"] = {}
        
        state["status"] = "checking_lock"
        
        logger.debug(
            "load_context_complete",
            request_id=request_id,
            user_id=str(user.id),
            onboarding_completed=state["onboarding_completed"],
            from_cache=state.get("cache_loaded", False),
            current_flow=state.get("current_flow"),
            pending_field=state.get("pending_field"),
        )
        
    finally:
        db.close()
    
    return state


def check_agent_lock_node(state: CoordinatorState) -> CoordinatorState:
    """
    Check if session is locked to an agent.
    
    This node prepares routing decision based on lock status.
    Also checks for intent change when locked, allowing users to
    break out of a flow by expressing a clear different intent.
    """
    from app.agents.common.intents import is_coordinator_command, detect_intent_fast
    
    request_id = state.get("request_id", "unknown")
    message = state.get("message_body", "")
    
    logger.debug("check_lock_start", request_id=request_id)
    
    # Check for coordinator commands first
    is_cmd, cmd_action = is_coordinator_command(message)
    if is_cmd:
        state["is_command"] = True
        state["command_action"] = cmd_action
        state["routing_method"] = "command"
        logger.debug("check_lock_command", request_id=request_id, command=cmd_action)
        return state
    
    state["is_command"] = False
    state["command_action"] = None
    
    # Check onboarding status
    if not state.get("onboarding_completed", False):
        state["selected_agent"] = AgentType.CONFIGURATION
        state["routing_method"] = "onboarding"
        state["routing_reason"] = "Onboarding not completed"
        state["routing_confidence"] = 1.0
        logger.debug("check_lock_onboarding", request_id=request_id)
        return state
    
    # Check for agent lock
    if state.get("agent_locked") and state.get("active_agent"):
        agent_str = state["active_agent"]
        current_agent = _map_agent_string(agent_str)
        
        # Check if user wants to change intent (break out of flow)
        intent_change = _check_intent_change(message, current_agent)
        
        if intent_change["changed"] and intent_change["new_agent"]:
            # User wants to switch - release lock and route to new agent
            state["selected_agent"] = intent_change["new_agent"]
            state["routing_method"] = "intent_change"
            state["routing_reason"] = intent_change.get("reason", "User intent changed")
            state["routing_confidence"] = intent_change.get("confidence", 0.8)
            # Mark that we need to release the lock
            state["new_agent_locked"] = False
            state["should_update_conversation"] = True
            logger.debug(
                "check_lock_intent_change",
                request_id=request_id,
                from_agent=agent_str,
                to_agent=intent_change["new_agent"].value,
            )
            return state
        
        # Continue with locked agent
        state["selected_agent"] = current_agent
        state["routing_method"] = "locked"
        state["routing_reason"] = f"Session locked to {agent_str}"
        state["routing_confidence"] = 1.0
        logger.debug(
            "check_lock_locked",
            request_id=request_id,
            agent=agent_str,
        )
        return state
    
    # Need to detect intent
    state["status"] = "detecting_intent"
    logger.debug("check_lock_unlocked", request_id=request_id)
    
    return state


def _check_intent_change(message: str, current_agent: AgentType) -> dict:
    """
    Check if user message indicates a change in intent.
    
    Uses keyword detection to quickly identify if user wants
    to do something clearly different from the current agent's scope.
    
    Args:
        message: User's message
        current_agent: Currently active agent
        
    Returns:
        Dict with: changed, new_agent, reason, confidence
    """
    from app.agents.common.intents import detect_intent_fast
    
    # Get detected intent from keywords
    detected = detect_intent_fast(message)
    
    # If no clear intent detected, don't change
    if detected is None:
        return {"changed": False}
    
    # Commands always trigger change
    if detected == AgentType.COORDINATOR:
        return {
            "changed": True,
            "new_agent": None,  # Will be handled by command handler
            "reason": "User issued a command",
            "confidence": 1.0,
        }
    
    # Check if detected intent differs from current agent
    if detected != current_agent:
        return {
            "changed": True,
            "new_agent": detected,
            "reason": f"Clear intent change from {current_agent.value} to {detected.value}",
            "confidence": 0.9,
        }
    
    return {"changed": False}


async def detect_intent_node(state: CoordinatorState) -> CoordinatorState:
    """
    Detect intent and select agent.
    
    Uses hybrid approach: keywords first, then LLM.
    """
    from app.agents.coordinator.router import detect_agent_for_message
    
    request_id = state.get("request_id", "unknown")
    message = state.get("message_body", "")
    
    logger.debug("detect_intent_start", request_id=request_id)
    
    # Detect intent
    result = await detect_agent_for_message(
        message=message,
        onboarding_completed=state.get("onboarding_completed", True),
        has_active_trip=state.get("has_active_trip", False),
        last_agent=state.get("active_agent"),
    )
    
    state["selected_agent"] = result.agent
    state["routing_method"] = result.method
    state["routing_confidence"] = result.confidence
    state["routing_reason"] = result.reason
    
    # Handle commands detected by router
    if result.is_command:
        state["is_command"] = True
        state["command_action"] = result.command_action
    
    state["status"] = "routing"
    
    logger.debug(
        "detect_intent_complete",
        request_id=request_id,
        agent=result.agent.value,
        method=result.method,
        confidence=result.confidence,
    )
    
    return state


async def handle_command_node(state: CoordinatorState) -> CoordinatorState:
    """
    Handle coordinator command.
    """
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.agents.coordinator.handlers.commands import handle_coordinator_command
    
    request_id = state.get("request_id", "unknown")
    command_action = state.get("command_action", "unknown")
    
    logger.debug("handle_command_start", request_id=request_id, command=command_action)
    
    db: Session = SessionLocal()
    try:
        response = await handle_coordinator_command(
            command_action=command_action,
            user_id=state["user_id"],
            user_name=state.get("user_name"),
            home_currency=state.get("home_currency"),
            timezone=state.get("timezone"),
            active_trip_name=None,  # Would need to load
            budget_status=None,
            active_agent=state.get("active_agent"),
            conversation_id=state.get("conversation_id"),
            db=db,
            request_id=request_id,
        )
        
        state["agent_response"] = response
        state["response_text"] = response.response_text
        state["status"] = "handling_response"
        
        # Mark for state update
        if response.release_lock:
            state["should_update_conversation"] = True
            state["new_agent_locked"] = False
            state["new_active_agent"] = None
        
    finally:
        db.close()
    
    return state


async def route_to_agent_node(state: CoordinatorState) -> CoordinatorState:
    """
    Route to the selected agent.
    
    Executes the appropriate handler based on selected_agent.
    """
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.agents.coordinator.handlers import (
        handle_configuration_agent,
        handle_ie_agent,
        handle_coach_agent,
    )
    
    request_id = state.get("request_id", "unknown")
    selected_agent = state.get("selected_agent", AgentType.UNKNOWN)
    
    logger.debug(
        "route_to_agent_start",
        request_id=request_id,
        agent=selected_agent.value,
    )
    
    db: Session = SessionLocal()
    try:
        if selected_agent == AgentType.CONFIGURATION:
            response = await handle_configuration_agent(
                user_id=state["user_id"],
                phone_number=state["phone_number"],
                message_body=state["message_body"],
                message_type=state.get("message_type", "text"),
                conversation_id=state.get("conversation_id"),
                profile_name=state.get("profile_name"),
                flow_data=state.get("flow_data", {}),
                handoff_context=state.get("handoff_context"),
                db=db,
                request_id=request_id,
            )
            
        elif selected_agent == AgentType.IE:
            response = await handle_ie_agent(
                user_id=state["user_id"],
                account_id=state.get("default_account_id"),
                message_body=state["message_body"],
                message_type=state.get("message_type", "text"),
                trip_id=state.get("active_trip_id"),
                card_id=None,
                media_url=state.get("media_url"),
                handoff_context=state.get("handoff_context"),
                request_id=request_id,
            )
            
        elif selected_agent == AgentType.COACH:
            response = await handle_coach_agent(
                user_id=state["user_id"],
                question=state["message_body"],
                handoff_context=state.get("handoff_context"),
                request_id=request_id,
            )
            
        else:
            # Unknown agent - use coach as fallback
            response = await handle_coach_agent(
                user_id=state["user_id"],
                question=state["message_body"],
                handoff_context=state.get("handoff_context"),
                request_id=request_id,
            )
        
        state["agent_response"] = response
        state["response_text"] = response.response_text
        state["status"] = "handling_response"
        
    finally:
        db.close()
    
    logger.debug(
        "route_to_agent_complete",
        request_id=request_id,
        agent=selected_agent.value,
        response_length=len(state.get("response_text", "")),
    )
    
    return state


def process_response_node(state: CoordinatorState) -> CoordinatorState:
    """
    Process agent response and prepare state updates.
    
    Handles:
    - Lock management (release/acquire)
    - Handoff preparation
    - State update preparation
    - Conversation sync from agent response
    """
    request_id = state.get("request_id", "unknown")
    response = state.get("agent_response")
    
    logger.debug("process_response_start", request_id=request_id)
    
    if not response:
        state["status"] = "error"
        state["errors"] = state.get("errors", []) + ["No agent response"]
        return state
    
    # Prepare state updates
    state["should_update_conversation"] = True
    
    # Handle lock based on response
    if response.release_lock:
        state["new_agent_locked"] = False
        state["new_lock_reason"] = None
    elif response.status.value == "awaiting_input":
        # Lock to this agent while awaiting input
        state["new_agent_locked"] = True
        state["new_active_agent"] = response.agent_name
        state["new_lock_reason"] = f"awaiting_input_{response.pending_field or 'response'}"
    
    # Handle flow updates from configuration agent
    if response.current_flow:
        state["new_flow"] = response.current_flow
    if response.flow_data:
        state["new_flow_data"] = response.flow_data
    
    # Handle step/pending_field updates from response
    # This is critical for maintaining conversation context
    if response.current_step:
        state["new_step"] = response.current_step
    elif response.pending_field:
        state["new_step"] = response.pending_field
    
    # If agent already persisted the conversation, use its conversation_id
    # and mark that we don't need to create a new one
    if response.conversation_persisted and response.conversation_id:
        state["conversation_id"] = response.conversation_id
        state["conversation_already_persisted"] = True
    
    # Handle handoff context
    if response.wants_handoff and response.handoff_context:
        state["new_handoff_context"] = response.handoff_context
        # Update selected agent for potential handoff
        state["selected_agent"] = _map_agent_string(response.handoff_to)
        state["handoff_count"] = state.get("handoff_count", 0) + 1
    else:
        state["new_handoff_context"] = None
    
    state["status"] = "updating_state"
    
    logger.debug(
        "process_response_complete",
        request_id=request_id,
        release_lock=response.release_lock,
        wants_handoff=response.wants_handoff,
    )
    
    return state


async def update_state_node(state: CoordinatorState) -> CoordinatorState:
    """
    Update conversation state in Azure Cache and database.
    
    This node:
    1. Updates the Azure Blob Cache (primary for hot data)
    2. Updates the database (for persistence) - ONLY if agent didn't already persist
    
    The Configuration Agent handles its own persistence, so we skip DB updates
    when conversation_already_persisted is True.
    """
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.storage.conversation_manager import (
        create_conversation,
        update_conversation,
    )
    from app.config import settings
    
    request_id = state.get("request_id", "unknown")
    phone_number = state["phone_number"]
    
    if not state.get("should_update_conversation"):
        state["status"] = "completed"
        return state
    
    logger.debug("update_state_start", request_id=request_id)
    
    # Determine flow and step - prioritize new_step from agent response
    new_flow = state.get("new_flow") or state.get("current_flow") or "general"
    new_step = state.get("new_step") or state.get("pending_field") or "idle"
    new_flow_data = state.get("new_flow_data") or state.get("flow_data") or {}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Update Azure Blob Cache (fast path for next request)
    # Always update cache with the latest state from the agent response
    # ─────────────────────────────────────────────────────────────────────────
    if settings.azure_storage_configured:
        try:
            from app.storage.conversation_cache import conversation_cache
            
            # Use explicit False instead of None to avoid issues
            agent_locked = state.get("new_agent_locked")
            if agent_locked is None:
                agent_locked = state.get("agent_locked", False)
            
            await conversation_cache.update_from_state(
                phone_number=phone_number,
                user_id=state["user_id"],
                current_flow=new_flow,
                current_step=new_step,  # Always pass the step
                pending_field=new_step if new_step != "idle" else None,
                flow_data=new_flow_data,
                user_name=state.get("user_name"),
                home_currency=state.get("home_currency"),
                timezone=state.get("timezone"),
                onboarding_completed=state.get("onboarding_completed", False),
                active_agent=state.get("new_active_agent") or state.get("active_agent"),
                agent_locked=agent_locked,
                lock_reason=state.get("new_lock_reason"),
                last_user_message=state.get("message_body"),
                last_bot_message=state.get("response_text"),
                conversation_id=state.get("conversation_id"),  # Sync conversation_id
            )
            
            logger.debug(
                "update_state_cache_saved",
                request_id=request_id,
                flow=new_flow,
                step=new_step,
            )
        except Exception as e:
            logger.warning("update_state_cache_error", error=str(e))
            # Continue with DB update
    
    # ─────────────────────────────────────────────────────────────────────────
    # Update database (for persistence)
    # SKIP if the agent already persisted the conversation (e.g., Configuration Agent)
    # ─────────────────────────────────────────────────────────────────────────
    if state.get("conversation_already_persisted"):
        # Agent already handled DB persistence, only update routing fields if needed
        conversation_id = state.get("conversation_id")
        if conversation_id and (state.get("new_agent_locked") is not None or state.get("new_active_agent")):
            db: Session = SessionLocal()
            try:
                from app.models import ConversationState as ConvModel
                conv = db.query(ConvModel).filter(ConvModel.id == conversation_id).first()
                if conv:
                    # Only update routing fields, not the conversation state itself
                    if state.get("new_active_agent") is not None:
                        conv.active_agent = state["new_active_agent"]
                    if state.get("new_agent_locked") is not None:
                        conv.agent_locked = state["new_agent_locked"]
                    else:
                        # Use False as default, never None
                        conv.agent_locked = False
                    if state.get("new_lock_reason") is not None:
                        conv.lock_reason = state["new_lock_reason"]
                    conv.handoff_context = state.get("new_handoff_context")
                    db.commit()
            except Exception as e:
                logger.error("update_state_routing_error", request_id=request_id, error=str(e))
            finally:
                db.close()
        
        state["status"] = "completed"
        logger.debug("update_state_complete", request_id=request_id)
        return state
    
    # ─────────────────────────────────────────────────────────────────────────
    # Full DB update (for agents that don't persist themselves)
    # ─────────────────────────────────────────────────────────────────────────
    db: Session = SessionLocal()
    try:
        conversation_id = state.get("conversation_id")
        user_id = state["user_id"]
        
        if conversation_id:
            # Update existing conversation
            update_conversation(
                db=db,
                conversation_id=conversation_id,
                flow=new_flow,
                step=new_step,
                state_data=new_flow_data,
                user_message=state.get("message_body"),
                bot_message=state.get("response_text"),
            )
            
            # Update agent routing fields manually
            from app.models import ConversationState as ConvModel
            conv = db.query(ConvModel).filter(ConvModel.id == conversation_id).first()
            if conv:
                if state.get("new_active_agent") is not None:
                    conv.active_agent = state["new_active_agent"]
                # Use False as default, never None
                agent_locked = state.get("new_agent_locked")
                conv.agent_locked = agent_locked if agent_locked is not None else False
                if state.get("new_lock_reason") is not None:
                    conv.lock_reason = state["new_lock_reason"]
                conv.handoff_context = state.get("new_handoff_context")
                db.commit()
        else:
            # Create new conversation
            result = create_conversation(
                db=db,
                user_id=user_id,
                flow=new_flow,
                step=new_step,
                state_data=new_flow_data,
            )
            if result.success and result.conversation:
                conv = result.conversation
                conv.active_agent = state.get("new_active_agent")
                # Use False as default, never None
                agent_locked = state.get("new_agent_locked")
                conv.agent_locked = agent_locked if agent_locked is not None else False
                conv.lock_reason = state.get("new_lock_reason")
                conv.handoff_context = state.get("new_handoff_context")
                db.commit()
                state["conversation_id"] = conv.id
        
        state["status"] = "completed"
        
        logger.debug("update_state_complete", request_id=request_id)
        
    except Exception as e:
        logger.error("update_state_error", request_id=request_id, error=str(e))
        state["errors"] = state.get("errors", []) + [str(e)]
        # Don't fail the request, just log the error
        state["status"] = "completed"
        
    finally:
        db.close()
    
    logger.debug("update_state_complete", request_id=request_id)
    
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def _map_agent_string(agent_str: str | None) -> AgentType:
    """Map agent string to AgentType."""
    if not agent_str:
        return AgentType.UNKNOWN
    
    mapping = {
        "configuration": AgentType.CONFIGURATION,
        "config": AgentType.CONFIGURATION,
        "ie": AgentType.IE,
        "expense": AgentType.IE,
        "coach": AgentType.COACH,
        "query": AgentType.COACH,
        "coordinator": AgentType.COORDINATOR,
    }
    return mapping.get(agent_str.lower(), AgentType.UNKNOWN)


# ─────────────────────────────────────────────────────────────────────────────
# Graph Compilation
# ─────────────────────────────────────────────────────────────────────────────

def create_coordinator_graph() -> StateGraph:
    """
    Create the Coordinator Agent graph.
    
    Flow:
    1. load_context → check_lock
    2. check_lock → (conditional):
       - "command" → handle_command → update_state → END
       - "onboarding" → route_to_agent → process_response → (conditional)
       - "locked" → route_to_agent → process_response → (conditional)
       - "unlocked" → detect_intent → route_to_agent → process_response → (conditional)
    3. process_response → (conditional):
       - "done" → update_state → END
       - "handoff" → route_to_agent (loop)
    
    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(CoordinatorState)
    
    # Add nodes
    graph.add_node("load_context", load_context_node)
    graph.add_node("check_lock", check_agent_lock_node)
    graph.add_node("detect_intent", detect_intent_node)
    graph.add_node("handle_command", handle_command_node)
    graph.add_node("route_to_agent", route_to_agent_node)
    graph.add_node("process_response", process_response_node)
    graph.add_node("update_state", update_state_node)
    
    # Set entry point
    graph.set_entry_point("load_context")
    
    # Add edges
    graph.add_edge("load_context", "check_lock")
    
    # Conditional from check_lock
    graph.add_conditional_edges(
        "check_lock",
        should_detect_intent,
        {
            "locked": "route_to_agent",
            "unlocked": "detect_intent",
            "onboarding": "route_to_agent",
            "command": "handle_command",
        }
    )
    
    graph.add_edge("detect_intent", "route_to_agent")
    graph.add_edge("handle_command", "update_state")
    graph.add_edge("route_to_agent", "process_response")
    
    # Conditional from process_response
    graph.add_conditional_edges(
        "process_response",
        should_continue_or_handoff,
        {
            "done": "update_state",
            "handoff": "route_to_agent",
        }
    )
    
    graph.add_edge("update_state", END)
    
    return graph


def compile_coordinator_graph():
    """Compile and return the coordinator graph."""
    graph = create_coordinator_graph()
    return graph.compile()


# Cached compiled graph
_compiled_graph = None


def get_coordinator_graph():
    """Get the cached compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_coordinator_graph()
    return _compiled_graph


def reset_graph():
    """Reset the cached graph (for testing)."""
    global _compiled_graph
    _compiled_graph = None



