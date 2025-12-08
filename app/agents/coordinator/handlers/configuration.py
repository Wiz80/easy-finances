"""
Handler for the Configuration Agent.

Wraps the ConfigurationAgent and converts its response to AgentResponse.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.common.response import (
    AgentResponse,
    AgentStatus,
    error_response,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


async def handle_configuration_agent(
    user_id: UUID,
    phone_number: str,
    message_body: str,
    message_type: str,
    conversation_id: UUID | None,
    profile_name: str | None,
    flow_data: dict[str, Any],
    handoff_context: dict[str, Any] | None,
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Execute the Configuration Agent and return unified response.
    
    Args:
        user_id: User UUID
        phone_number: User's phone number
        message_body: Message text
        message_type: Type of message
        conversation_id: Active conversation ID
        profile_name: WhatsApp profile name
        flow_data: Current flow data
        handoff_context: Context from previous agent
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with configuration result
    """
    try:
        from app.agents.configuration_agent import process_message
        
        logger.debug(
            "configuration_handler_start",
            request_id=request_id,
            user_id=str(user_id),
            has_conversation=conversation_id is not None,
        )
        
        # Check if we have handoff context with specific flow
        target_flow = None
        if handoff_context:
            target_flow = handoff_context.get("target_flow")
        
        # Execute configuration agent
        result = await process_message(
            user_id=user_id,
            phone_number=phone_number,
            message_body=message_body,
            db=db,
            message_type=message_type,
            conversation_id=conversation_id,
            profile_name=profile_name,
            request_id=request_id,
        )
        
        # Convert to AgentResponse
        response = AgentResponse(
            response_text=result.response_text or "Ocurrió un error.",
            status=_map_config_status(result.status),
            agent_name="configuration",
            request_id=request_id,
            # Flow state
            current_flow=result.current_flow,
            pending_field=result.pending_field,
            flow_data=result.flow_data,
            # Lock management
            release_lock=_should_release_lock(result),
            continue_flow=result.pending_field is not None,
            # Handoff (config agent might want to transfer)
            handoff_to=_check_handoff(result),
            # Errors
            errors=result.errors,
        )
        
        logger.debug(
            "configuration_handler_complete",
            request_id=request_id,
            status=response.status.value,
            release_lock=response.release_lock,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "configuration_handler_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error en la configuración. Por favor intenta de nuevo.",
            agent_name="configuration",
            errors=[str(e)],
            request_id=request_id,
        )


def _map_config_status(status: str) -> AgentStatus:
    """Map configuration agent status to AgentStatus."""
    mapping = {
        "completed": AgentStatus.COMPLETED,
        "awaiting_input": AgentStatus.AWAITING_INPUT,
        "error": AgentStatus.ERROR,
        "processing": AgentStatus.AWAITING_INPUT,
    }
    return mapping.get(status, AgentStatus.COMPLETED)


def _should_release_lock(result) -> bool:
    """
    Determine if the lock should be released.
    
    Release when:
    - Flow is completed (no pending field)
    - Status is error
    - Flow is "general" (not in a specific flow)
    """
    if result.status == "error":
        return True
    if result.current_flow == "general":
        return True
    if result.pending_field is None and result.status == "completed":
        return True
    return False


def _check_handoff(result) -> str | None:
    """
    Check if configuration agent wants to hand off.
    
    Hand off to coordinator when onboarding is complete and
    no specific flow is active.
    """
    # Check flow_data for handoff signals
    flow_data = result.flow_data or {}
    if flow_data.get("handoff_to"):
        return flow_data.get("handoff_to")
    
    # After completing onboarding, return to coordinator
    if result.current_flow == "general" and not result.pending_field:
        return "coordinator"
    
    return None

