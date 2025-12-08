"""
Coordinator Agent - Main Entry Point.

The Coordinator Agent is the central routing hub for all WhatsApp messages.
It determines which specialized agent should handle each message:
- ConfigurationAgent: User setup, trips, cards, budgets
- IEAgent: Expense extraction and storage  
- CoachAgent: Financial queries and reports

Features:
- Sticky sessions: Keep user with same agent during a flow
- Handoff protocol: Agents can transfer conversations
- Special commands: cancel, menu, help
- Hybrid intent detection: keywords + LLM

Usage:
    from app.agents.coordinator import process_message
    
    response = await process_message(
        phone_number="+573115084628",
        message_body="Gasté 50 soles en taxi",
    )
    
    print(response.response_text)
    # "✅ 🚕 Gasto registrado: Taxi: 50.00 PEN"
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.agents.coordinator.graph import get_coordinator_graph
from app.agents.coordinator.state import CoordinatorState, create_initial_state
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CoordinatorResult:
    """
    Result from the Coordinator Agent.
    
    Attributes:
        response_text: Text to send to user via WhatsApp
        success: Whether processing completed successfully
        agent_used: Which agent handled the request
        routing_method: How the agent was selected
        user_id: User UUID
        conversation_id: Conversation UUID
        errors: List of errors (if any)
    """
    
    response_text: str
    success: bool = True
    agent_used: str = "coordinator"
    routing_method: str = ""
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    request_id: str = ""
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response_text": self.response_text,
            "success": self.success,
            "agent_used": self.agent_used,
            "routing_method": self.routing_method,
            "user_id": str(self.user_id) if self.user_id else None,
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "request_id": self.request_id,
            "errors": self.errors,
        }
    
    def __repr__(self) -> str:
        return (
            f"CoordinatorResult(success={self.success}, "
            f"agent={self.agent_used}, method={self.routing_method})"
        )


async def process_message(
    phone_number: str,
    message_body: str,
    message_type: str = "text",
    media_url: str | None = None,
    message_sid: str | None = None,
    profile_name: str | None = None,
    request_id: str | None = None,
) -> CoordinatorResult:
    """
    Process a WhatsApp message through the Coordinator.
    
    This is the main entry point for all incoming messages.
    The Coordinator will:
    1. Identify or create the user
    2. Load conversation context
    3. Determine which agent should handle the message
    4. Route to the appropriate agent
    5. Handle responses and handoffs
    6. Update conversation state
    
    Args:
        phone_number: User's WhatsApp number (e.g., "+573115084628")
        message_body: Text content of the message
        message_type: Type of message ("text", "audio", "image")
        media_url: URL for media content (for audio/image)
        message_sid: Twilio message SID (for idempotency)
        profile_name: WhatsApp profile name
        request_id: Request ID for tracing
        
    Returns:
        CoordinatorResult with response and metadata
        
    Example:
        >>> result = await process_message(
        ...     phone_number="+573115084628",
        ...     message_body="Gasté 50 soles en taxi",
        ... )
        >>> print(result.response_text)
        "✅ 🚕 Gasto registrado: Taxi: 50.00 PEN"
        >>> print(result.agent_used)
        "ie"
    """
    import uuid
    
    request_id = request_id or str(uuid.uuid4())
    
    logger.info(
        "coordinator_process_start",
        request_id=request_id,
        phone=phone_number[-4:],
        message_type=message_type,
        message_preview=message_body[:50] if message_body else None,
    )
    
    try:
        # Create initial state
        initial_state = create_initial_state(
            phone_number=phone_number,
            message_body=message_body,
            message_type=message_type,
            media_url=media_url,
            message_sid=message_sid,
            profile_name=profile_name,
            request_id=request_id,
        )
        
        # Get compiled graph
        graph = get_coordinator_graph()
        
        # Execute graph
        logger.debug("coordinator_graph_invoke_start", request_id=request_id)
        final_state = await graph.ainvoke(initial_state)
        logger.debug("coordinator_graph_invoke_complete", request_id=request_id)
        
        # Extract result
        result = CoordinatorResult(
            response_text=final_state.get("response_text", ""),
            success=final_state.get("status") == "completed",
            agent_used=_get_agent_used(final_state),
            routing_method=final_state.get("routing_method", ""),
            user_id=final_state.get("user_id"),
            conversation_id=final_state.get("conversation_id"),
            request_id=request_id,
            errors=final_state.get("errors", []),
        )
        
        logger.info(
            "coordinator_process_complete",
            request_id=request_id,
            success=result.success,
            agent=result.agent_used,
            method=result.routing_method,
            response_length=len(result.response_text),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "coordinator_process_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        return CoordinatorResult(
            response_text="⚠️ Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo.",
            success=False,
            request_id=request_id,
            errors=[str(e)],
        )


def _get_agent_used(state: CoordinatorState) -> str:
    """Extract which agent was used from final state."""
    response = state.get("agent_response")
    if response:
        return response.agent_name
    
    selected = state.get("selected_agent")
    if selected:
        return selected.value
    
    return "coordinator"


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

async def handle_whatsapp_message(
    from_number: str,
    body: str,
    message_sid: str | None = None,
    media_url: str | None = None,
    media_type: str | None = None,
    profile_name: str | None = None,
) -> str:
    """
    High-level function to handle a WhatsApp message.
    
    This is a convenience wrapper that returns just the response text.
    
    Args:
        from_number: WhatsApp number (e.g., "whatsapp:+573115084628")
        body: Message text
        message_sid: Twilio message SID
        media_url: URL for media
        media_type: MIME type of media
        profile_name: WhatsApp profile name
        
    Returns:
        Response text to send back
    """
    # Clean phone number
    phone_number = from_number.replace("whatsapp:", "")
    
    # Determine message type
    message_type = "text"
    if media_url and media_type:
        if "audio" in media_type:
            message_type = "audio"
        elif "image" in media_type:
            message_type = "image"
        elif "pdf" in media_type or "document" in media_type:
            message_type = "document"
    
    # Process through coordinator
    result = await process_message(
        phone_number=phone_number,
        message_body=body,
        message_type=message_type,
        media_url=media_url,
        message_sid=message_sid,
        profile_name=profile_name,
    )
    
    return result.response_text


# Aliases
process = process_message
handle = handle_whatsapp_message

