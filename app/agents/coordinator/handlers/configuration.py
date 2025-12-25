"""
Handler for the Configuration Agent.

Wraps the ConfigurationAgent and converts its response to AgentResponse.
Uses the agent's native to_agent_response() method for clean conversion.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.common.response import (
    AgentResponse,
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
        
        # Use agent's native conversion method
        response = result.to_agent_response(request_id)
        
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

