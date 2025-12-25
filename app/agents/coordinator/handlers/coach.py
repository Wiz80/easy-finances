"""
Handler for the Coach Agent.

Wraps the CoachAgent and converts its response to AgentResponse.
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


async def handle_coach_agent(
    user_id: UUID,
    question: str,
    handoff_context: dict[str, Any] | None,
    request_id: str,
) -> AgentResponse:
    """
    Execute the Coach Agent and return unified response.
    
    Args:
        user_id: User UUID
        question: User's question about finances
        handoff_context: Context from previous agent
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with coach result
    """
    try:
        from app.agents.coach_agent import ask_coach
        
        logger.debug(
            "coach_handler_start",
            request_id=request_id,
            user_id=str(user_id),
            question_preview=question[:50],
        )
        
        # Check for question in handoff context
        actual_question = question
        if handoff_context and "question" in handoff_context:
            actual_question = handoff_context["question"]
        
        # Execute coach agent (async)
        result = await ask_coach(
            user_id=str(user_id),
            question=actual_question,
            request_id=request_id,
        )
        
        # Use agent's native conversion method
        response = result.to_agent_response()
        
        logger.debug(
            "coach_handler_complete",
            request_id=request_id,
            status=response.status.value,
            response_length=len(response.response_text),
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "coach_handler_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error procesando tu consulta. Por favor intenta de nuevo.",
            agent_name="coach",
            errors=[str(e)],
            request_id=request_id,
        )

