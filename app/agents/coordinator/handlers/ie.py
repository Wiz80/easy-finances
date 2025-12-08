"""
Handler for the IE (Information Extraction) Agent.

Wraps the IEAgent and converts its response to AgentResponse.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.common.response import (
    AgentResponse,
    AgentStatus,
    error_response,
    success_response,
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
        
        # Build response text
        response_text = _build_expense_response(result)
        
        # Convert to AgentResponse
        response = AgentResponse(
            response_text=response_text,
            status=_map_ie_status(result.status),
            agent_name="ie",
            request_id=request_id,
            confidence=result.confidence,
            # Created entity
            created_expense_id=result.expense_id,
            # Lock management - IE agent usually completes in one turn
            release_lock=True,
            continue_flow=False,
            # Handoff back to coordinator after expense
            handoff_to="coordinator",
            handoff_reason="expense_completed",
            # Errors
            errors=result.errors,
        )
        
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


def _map_ie_status(status: str) -> AgentStatus:
    """Map IE agent status to AgentStatus."""
    mapping = {
        "completed": AgentStatus.COMPLETED,
        "low_confidence": AgentStatus.COMPLETED,
        "error": AgentStatus.ERROR,
        "pending": AgentStatus.AWAITING_INPUT,
    }
    return mapping.get(status, AgentStatus.COMPLETED)


def _build_expense_response(result) -> str:
    """Build user-friendly response for expense result."""
    if result.is_duplicate:
        return "ℹ️ Este gasto ya fue registrado anteriormente."
    
    if result.status == "error":
        error_msg = result.errors[0] if result.errors else "Error desconocido"
        return f"⚠️ No pude registrar el gasto: {error_msg}"
    
    if result.status == "low_confidence":
        expense = result.extracted_expense
        if expense:
            return (
                f"🤔 Registré el gasto pero con poca confianza:\n"
                f"• Monto: {expense.amount} {expense.currency}\n"
                f"• Descripción: {expense.description or 'Sin descripción'}\n"
                f"¿Es correcto? Si no, puedes corregirlo."
            )
        return "🤔 No estoy seguro de haber entendido bien. ¿Puedes darme más detalles?"
    
    # Success
    expense = result.extracted_expense
    if expense:
        amount_str = f"{expense.amount:,.2f}" if expense.amount else "?"
        currency = expense.currency or "?"
        description = expense.description or "Gasto"
        category = expense.category_candidate or ""
        
        # Category emoji
        category_emoji = _get_category_emoji(category)
        
        return (
            f"✅ {category_emoji} Gasto registrado:\n"
            f"• {description}: {amount_str} {currency}"
        )
    
    return "✅ Gasto registrado correctamente."


def _get_category_emoji(category: str) -> str:
    """Get emoji for expense category."""
    emoji_map = {
        "FOOD": "🍔",
        "LODGING": "🏨",
        "TRANSPORT": "🚕",
        "TOURISM": "🎭",
        "SHOPPING": "🛍️",
        "MISC": "📦",
    }
    return emoji_map.get(category.upper(), "💰")

