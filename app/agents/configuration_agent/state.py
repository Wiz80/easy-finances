"""
Configuration Agent State Schema.

Defines the state that flows through the LangGraph nodes for
conversational user configuration (onboarding, trip setup, budgets, etc.)
"""

from datetime import datetime
from typing import Any, Literal, TypedDict
from uuid import UUID


# Conversation flows supported by the Configuration Agent
FlowType = Literal[
    "onboarding",      # New user setup (name, currency, timezone)
    "trip_setup",      # Configure a trip (name, dates, destination)
    "card_setup",      # Register a card/account
    "budget_config",   # Configure budget allocations
    "general",         # General conversation / help
    "unknown",         # Intent not yet determined
]

# Agent execution status
AgentStatus = Literal[
    "processing",      # Processing message
    "awaiting_input",  # Waiting for user response
    "completed",       # Flow completed successfully
    "error",           # Error occurred
]


class MessageEntry(TypedDict):
    """A single message in the conversation history."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str


class ConfigurationAgentState(TypedDict, total=False):
    """
    State schema for the Configuration Agent.
    
    This state flows through all LangGraph nodes and contains:
    - User context (user_id, phone, onboarding status)
    - Conversation context (current flow, accumulated data)
    - Message data (incoming message, response to send)
    - LLM interaction (messages for chat completion)
    
    The agent uses LLM to:
    - Understand user intent from natural language
    - Determine what information is needed
    - Generate conversational responses
    - Validate and persist data
    """
    
    # =========================================================================
    # Request Identity
    # =========================================================================
    request_id: str  # Unique ID for tracing
    
    # =========================================================================
    # User Context
    # =========================================================================
    user_id: UUID
    phone_number: str
    user_name: str | None  # User's name (if known)
    home_currency: str | None  # User's home currency
    timezone: str | None  # User's timezone
    onboarding_completed: bool  # Whether user finished onboarding
    
    # =========================================================================
    # Conversation Context
    # =========================================================================
    conversation_id: UUID | None  # Active conversation ID (from DB)
    current_flow: FlowType  # Current conversation flow
    flow_data: dict[str, Any]  # Accumulated data for current flow
    # Example flow_data for trip_setup:
    # {
    #     "name": "Ecuador Adventure",
    #     "start_date": "2024-12-15",
    #     "end_date": "2024-12-30",
    #     "country": "EC",
    #     "city": "Quito",
    #     "currency": "USD"
    # }
    
    pending_field: str | None  # Field we're waiting for user to provide
    # Examples: "name", "currency", "start_date", "confirm"
    
    # =========================================================================
    # Incoming Message
    # =========================================================================
    message_body: str  # User's message text
    message_type: str  # Type: text, audio, image
    profile_name: str | None  # WhatsApp profile name
    
    # =========================================================================
    # LLM Context (for chat completion)
    # =========================================================================
    system_prompt: str | None  # System prompt for LLM
    messages: list[MessageEntry]  # Conversation history for LLM
    
    # =========================================================================
    # Detected Intent & Entities
    # =========================================================================
    detected_intent: str | None  # Intent detected from message
    # Possible intents: 
    # - onboarding_start, provide_name, provide_currency, provide_timezone
    # - trip_create, trip_provide_name, trip_provide_dates, trip_confirm
    # - budget_create, budget_provide_amount, budget_confirm
    # - help, cancel, confirm, deny
    
    extracted_entities: dict[str, Any]  # Entities extracted from message
    # Example: {"name": "Harrison", "currency": "COP"}
    
    # =========================================================================
    # Response
    # =========================================================================
    response_text: str | None  # Text to send back to user
    
    # =========================================================================
    # Persistence Actions
    # =========================================================================
    should_persist: bool  # Whether to persist changes to DB
    persist_type: str | None  # What to persist: "user", "trip", "card", "budget"
    persist_data: dict[str, Any] | None  # Data to persist
    
    # =========================================================================
    # Status & Errors
    # =========================================================================
    status: AgentStatus
    errors: list[str]


def create_initial_state(
    user_id: UUID,
    phone_number: str,
    message_body: str,
    message_type: str = "text",
    conversation_id: UUID | None = None,
    current_flow: FlowType = "unknown",
    flow_data: dict[str, Any] | None = None,
    user_name: str | None = None,
    home_currency: str | None = None,
    timezone: str | None = None,
    onboarding_completed: bool = False,
    profile_name: str | None = None,
    request_id: str | None = None,
) -> ConfigurationAgentState:
    """
    Create initial state for Configuration Agent execution.
    
    Args:
        user_id: User UUID
        phone_number: User's phone number
        message_body: Text of incoming message
        message_type: Type of message (text, audio, image)
        conversation_id: Active conversation ID (if any)
        current_flow: Current conversation flow
        flow_data: Accumulated data for current flow
        user_name: User's name (if known)
        home_currency: User's home currency (if known)
        timezone: User's timezone (if known)
        onboarding_completed: Whether onboarding is done
        profile_name: WhatsApp profile name
        request_id: Request ID for tracing
        
    Returns:
        ConfigurationAgentState ready for graph execution
    """
    import uuid
    
    return ConfigurationAgentState(
        request_id=request_id or str(uuid.uuid4()),
        # User context
        user_id=user_id,
        phone_number=phone_number,
        user_name=user_name,
        home_currency=home_currency,
        timezone=timezone,
        onboarding_completed=onboarding_completed,
        # Conversation context
        conversation_id=conversation_id,
        current_flow=current_flow,
        flow_data=flow_data or {},
        pending_field=None,
        # Incoming message
        message_body=message_body,
        message_type=message_type,
        profile_name=profile_name,
        # LLM context
        system_prompt=None,
        messages=[],
        # Detection
        detected_intent=None,
        extracted_entities={},
        # Response
        response_text=None,
        # Persistence
        should_persist=False,
        persist_type=None,
        persist_data=None,
        # Status
        status="processing",
        errors=[],
    )

