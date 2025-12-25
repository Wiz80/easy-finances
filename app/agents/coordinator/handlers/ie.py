"""
Handler for the IE (Information Extraction) Agent.

Wraps the IEAgent and converts its response to AgentResponse.
Uses the agent's native to_agent_response() method for clean conversion.
"""

from typing import Any
from uuid import UUID

from app.agents.common.response import (
    AgentResponse,
    error_response,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


async def handle_ie_agent(
    user_id: UUID,
    account_id: UUID | None,
    message_body: str,
    message_type: str,
    trip_id: UUID | None,
    card_id: UUID | None,
    media_url: str | None,
    handoff_context: dict[str, Any] | None,
    request_id: str,
) -> AgentResponse:
    """
    Execute the IE Agent and return unified response.
    
    Args:
        user_id: User UUID
        account_id: Account UUID for the expense
        message_body: Message text (expense description)
        message_type: Type of message (text, audio, image)
        trip_id: Active trip ID (optional)
        card_id: Card ID (optional)
        media_url: URL for media (audio/image)
        handoff_context: Context from previous agent
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with expense result
    """
    try:
        from app.agents.ie_agent import process_expense
        
        logger.debug(
            "ie_handler_start",
            request_id=request_id,
            user_id=str(user_id),
            message_type=message_type,
        )
        
        # If account_id is None, we need to handle this
        if account_id is None:
            return error_response(
                text="⚠️ No tienes una cuenta configurada. Por favor configura una cuenta primero.",
                agent_name="ie",
                errors=["No account configured"],
                request_id=request_id,
            )
        
        # Determine input type
        input_type = _map_message_type(message_type)
        
        # Get raw input (text or would need to download media)
        raw_input = message_body
        if handoff_context and "raw_input" in handoff_context:
            raw_input = handoff_context["raw_input"]
        
        # Execute IE agent (it's synchronous)
        result = process_expense(
            user_id=user_id,
            account_id=account_id,
            raw_input=raw_input,
            input_type=input_type,
            trip_id=trip_id,
            card_id=card_id,
            request_id=request_id,
        )
        
        # Use agent's native conversion method
        response = result.to_agent_response(request_id)
        
        logger.debug(
            "ie_handler_complete",
            request_id=request_id,
            status=response.status.value,
            expense_id=str(result.expense_id) if result.expense_id else None,
            confidence=result.confidence,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "ie_handler_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error registrando el gasto. Por favor intenta de nuevo.",
            agent_name="ie",
            errors=[str(e)],
            request_id=request_id,
        )


def _map_message_type(message_type: str) -> str:
    """Map WhatsApp message type to IE agent input type."""
    mapping = {
        "text": "text",
        "audio": "audio",
        "image": "image",
        "document": "receipt",
    }
    return mapping.get(message_type, "text")

