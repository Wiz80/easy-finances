"""
Configuration Agent - Main Entry Point.

The Configuration Agent handles conversational user configuration via WhatsApp:
- User onboarding (name, currency, timezone)
- Trip setup (name, dates, destination, currency)
- Budget configuration (allocations by category)
- Card/Account registration

Usage:
    from app.agents.configuration_agent import process_message
    
    result = await process_message(
        user_id=user.id,
        phone_number="+573115084628",
        message_body="Hola, quiero configurar un viaje",
        db=session,
    )
    
    if result.success:
        # Send result.response_text to user via WhatsApp
        print(result.response_text)
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.configuration_agent.graph import compile_configuration_agent_graph
from app.agents.configuration_agent.state import (
    AgentStatus,
    ConfigurationAgentState,
    FlowType,
    create_initial_state,
)
from app.logging_config import get_logger
from app.models import ConversationState, User

logger = get_logger(__name__)


class ConfigurationAgentResult:
    """
    Result object from Configuration Agent execution.
    
    Provides convenient access to execution results.
    """
    
    def __init__(self, state: ConfigurationAgentState):
        self._state = state
    
    @property
    def success(self) -> bool:
        """Whether the agent completed successfully."""
        return self._state.get("status") == "completed"
    
    @property
    def status(self) -> AgentStatus:
        """Final status of the agent execution."""
        return self._state.get("status", "error")
    
    @property
    def response_text(self) -> str:
        """Response text to send to the user."""
        return self._state.get("response_text", "")
    
    @property
    def current_flow(self) -> FlowType:
        """Current conversation flow."""
        return self._state.get("current_flow", "unknown")
    
    @property
    def pending_field(self) -> str | None:
        """Field we're waiting for from the user."""
        return self._state.get("pending_field")
    
    @property
    def flow_data(self) -> dict[str, Any]:
        """Accumulated data for the current flow."""
        return self._state.get("flow_data", {})
    
    @property
    def errors(self) -> list[str]:
        """List of error messages."""
        return self._state.get("errors", [])
    
    @property
    def conversation_id(self) -> UUID | None:
        """Active conversation ID."""
        return self._state.get("conversation_id")
    
    @property
    def state(self) -> ConfigurationAgentState:
        """Full state dict."""
        return self._state
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "status": self.status,
            "response_text": self.response_text,
            "current_flow": self.current_flow,
            "pending_field": self.pending_field,
            "errors": self.errors,
        }
    
    def __repr__(self) -> str:
        return (
            f"ConfigurationAgentResult(success={self.success}, "
            f"flow={self.current_flow}, response_length={len(self.response_text)})"
        )


async def process_message(
    user_id: UUID,
    phone_number: str,
    message_body: str,
    db: Session,
    message_type: str = "text",
    conversation_id: UUID | None = None,
    profile_name: str | None = None,
    request_id: str | None = None,
) -> ConfigurationAgentResult:
    """
    Process a message through the Configuration Agent.
    
    This is the main entry point for the Configuration Agent. It:
    1. Loads user and conversation context from DB
    2. Detects intent using LLM
    3. Processes the appropriate flow
    4. Generates a natural language response
    5. Persists any changes
    
    Args:
        user_id: User UUID
        phone_number: User's phone number
        message_body: Text content of the message
        db: Database session
        message_type: Type of message (text, audio, image)
        conversation_id: Active conversation ID (if known)
        profile_name: WhatsApp profile name
        request_id: Request ID for tracing
        
    Returns:
        ConfigurationAgentResult with response and state
        
    Example:
        >>> result = await process_message(
        ...     user_id=user.id,
        ...     phone_number="+573115084628",
        ...     message_body="Hola, me llamo Harrison",
        ...     db=session,
        ... )
        >>> print(result.response_text)
        "¡Mucho gusto, Harrison! ¿Cuál es tu moneda base?"
    """
    import uuid
    
    # Generate request ID if not provided
    request_id = request_id or str(uuid.uuid4())
    
    logger.info(
        "configuration_agent_start",
        request_id=request_id,
        user_id=str(user_id),
        message_preview=message_body[:50] if message_body else None,
    )
    
    try:
        # Load user to get context
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return ConfigurationAgentResult(ConfigurationAgentState(
                request_id=request_id,
                user_id=user_id,
                phone_number=phone_number,
                message_body=message_body,
                status="error",
                response_text="Error: Usuario no encontrado.",
                errors=["User not found"],
            ))
        
        # Load active conversation if exists
        current_flow: FlowType = "unknown"
        flow_data = {}
        
        if conversation_id:
            conversation = db.query(ConversationState).filter(
                ConversationState.id == conversation_id
            ).first()
            if conversation and conversation.is_active:
                current_flow = conversation.current_flow
                flow_data = conversation.state_data or {}
        
        # Create initial state
        initial_state = create_initial_state(
            user_id=user_id,
            phone_number=phone_number,
            message_body=message_body,
            message_type=message_type,
            conversation_id=conversation_id,
            current_flow=current_flow,
            flow_data=flow_data,
            user_name=user.nickname or user.full_name,
            home_currency=user.home_currency,
            timezone=user.timezone,
            onboarding_completed=user.onboarding_status == "completed",
            profile_name=profile_name,
            request_id=request_id,
        )
        
        # Compile and run the graph
        graph = compile_configuration_agent_graph(db)
        
        logger.debug("configuration_agent_graph_invoke_start", request_id=request_id)
        final_state = graph.invoke(initial_state)
        logger.debug("configuration_agent_graph_invoke_complete", request_id=request_id)
        
        # Create result object
        result = ConfigurationAgentResult(final_state)
        
        logger.info(
            "configuration_agent_complete",
            request_id=request_id,
            success=result.success,
            flow=result.current_flow,
            response_length=len(result.response_text),
            error_count=len(result.errors),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "configuration_agent_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        # Return error result
        return ConfigurationAgentResult(ConfigurationAgentState(
            request_id=request_id,
            user_id=user_id,
            phone_number=phone_number,
            message_body=message_body,
            status="error",
            response_text="⚠️ Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo.",
            errors=[f"Agent execution failed: {str(e)}"],
        ))


# Convenience alias
process = process_message

