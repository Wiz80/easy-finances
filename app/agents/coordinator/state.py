"""
Coordinator Agent State Schema.

Defines the state that flows through the LangGraph nodes for
multi-agent routing and orchestration.
"""

from datetime import datetime
from typing import Any, Literal, TypedDict
from uuid import UUID

from app.agents.common.intents import AgentType
from app.agents.common.response import AgentResponse


# Coordinator execution status
CoordinatorStatus = Literal[
    "loading",          # Loading user/conversation context
    "checking_lock",    # Checking for agent lock
    "detecting_intent", # Detecting intent for routing
    "routing",          # Routing to agent
    "processing",       # Agent is processing
    "handling_response",# Processing agent response
    "updating_state",   # Updating conversation state
    "completed",        # Finished successfully
    "error",            # Error occurred
]


class CoordinatorState(TypedDict, total=False):
    """
    State schema for the Coordinator Agent.
    
    This state flows through all LangGraph nodes and contains:
    - Request identity (for tracing)
    - User context (user_id, onboarding status)
    - Conversation context (active agent, lock status)
    - Routing decision (selected agent, method)
    - Agent response (from specialized agent)
    - Output (final response to user)
    
    The Coordinator:
    1. Loads user/conversation context
    2. Checks if there's an active agent lock
    3. If locked: routes to that agent
    4. If not: detects intent and routes accordingly
    5. Processes agent response (handles handoffs)
    6. Updates conversation state
    7. Returns unified response
    """
    
    # =========================================================================
    # Request Identity
    # =========================================================================
    request_id: str  # Unique ID for tracing
    
    # =========================================================================
    # Input Message
    # =========================================================================
    phone_number: str
    message_body: str
    message_type: str  # "text", "audio", "image"
    media_url: str | None  # URL for media messages
    message_sid: str | None  # Twilio message ID
    profile_name: str | None  # WhatsApp profile name
    
    # =========================================================================
    # User Context (loaded from DB)
    # =========================================================================
    user_id: UUID
    user_name: str | None
    home_currency: str | None
    timezone: str | None
    onboarding_completed: bool
    has_active_trip: bool
    active_trip_id: UUID | None
    default_account_id: UUID | None
    
    # =========================================================================
    # Conversation Context (loaded from DB)
    # =========================================================================
    conversation_id: UUID | None
    active_agent: str | None  # Currently assigned agent
    agent_locked: bool  # Is session locked to agent?
    lock_reason: str | None
    current_flow: str | None  # Flow within agent
    current_step: str | None  # Step within flow
    flow_data: dict[str, Any]  # Accumulated flow data
    handoff_context: dict[str, Any] | None  # Context from previous agent
    last_bot_message: str | None
    
    # =========================================================================
    # Routing Decision
    # =========================================================================
    selected_agent: AgentType  # Agent to route to
    routing_method: str  # "locked", "onboarding", "keyword", "llm", "command"
    routing_confidence: float
    routing_reason: str | None
    
    # Command handling (for special commands)
    is_command: bool
    command_action: str | None  # "cancel", "menu", "help", etc.
    
    # =========================================================================
    # Agent Execution
    # =========================================================================
    agent_response: AgentResponse | None  # Response from specialized agent
    handoff_count: int  # Number of handoffs this request (prevent loops)
    
    # =========================================================================
    # Output
    # =========================================================================
    response_text: str  # Final text to send to user
    
    # =========================================================================
    # State Updates (to persist)
    # =========================================================================
    should_update_conversation: bool
    new_active_agent: str | None  # New agent to set
    new_agent_locked: bool | None  # New lock status
    new_lock_reason: str | None
    new_flow: str | None
    new_step: str | None
    new_flow_data: dict[str, Any] | None
    new_handoff_context: dict[str, Any] | None
    
    # =========================================================================
    # Status & Errors
    # =========================================================================
    status: CoordinatorStatus
    errors: list[str]


def create_initial_state(
    phone_number: str,
    message_body: str,
    message_type: str = "text",
    media_url: str | None = None,
    message_sid: str | None = None,
    profile_name: str | None = None,
    request_id: str | None = None,
) -> CoordinatorState:
    """
    Create initial state for Coordinator Agent execution.
    
    Args:
        phone_number: User's phone number
        message_body: Message text content
        message_type: Type of message (text, audio, image)
        media_url: URL for media content
        message_sid: Twilio message SID
        profile_name: WhatsApp profile name
        request_id: Optional request ID for tracing
        
    Returns:
        CoordinatorState ready for graph execution
    """
    import uuid
    
    return CoordinatorState(
        # Request identity
        request_id=request_id or str(uuid.uuid4()),
        
        # Input message
        phone_number=phone_number,
        message_body=message_body,
        message_type=message_type,
        media_url=media_url,
        message_sid=message_sid,
        profile_name=profile_name,
        
        # User context (will be loaded)
        user_id=None,  # type: ignore
        user_name=None,
        home_currency=None,
        timezone=None,
        onboarding_completed=False,
        has_active_trip=False,
        active_trip_id=None,
        default_account_id=None,
        
        # Conversation context (will be loaded)
        conversation_id=None,
        active_agent=None,
        agent_locked=False,
        lock_reason=None,
        current_flow=None,
        current_step=None,
        flow_data={},
        handoff_context=None,
        last_bot_message=None,
        
        # Routing (will be determined)
        selected_agent=AgentType.UNKNOWN,
        routing_method="",
        routing_confidence=0.0,
        routing_reason=None,
        is_command=False,
        command_action=None,
        
        # Agent execution
        agent_response=None,
        handoff_count=0,
        
        # Output
        response_text="",
        
        # State updates
        should_update_conversation=False,
        new_active_agent=None,
        new_agent_locked=None,
        new_lock_reason=None,
        new_flow=None,
        new_step=None,
        new_flow_data=None,
        new_handoff_context=None,
        
        # Status
        status="loading",
        errors=[],
    )

