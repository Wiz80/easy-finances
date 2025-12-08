"""
Handler for the Coach Agent.

Wraps the CoachAgent and converts its response to AgentResponse.
"""

from typing import Any
from uuid import UUID

from app.agents.common.response import (
    AgentResponse,
    AgentStatus,
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
        
        # Convert to AgentResponse
        response = AgentResponse(
            response_text=result.response or "No pude procesar tu consulta.",
            status=_map_coach_status(result.status),
            agent_name="coach",
            request_id=request_id,
            # Lock management - queries are usually one-turn
            release_lock=True,
            continue_flow=False,
            # Handoff back to coordinator
            handoff_to="coordinator",
            handoff_reason="query_completed",
            # Errors
            errors=result.errors,
        )
        
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


def _map_coach_status(status: str) -> AgentStatus:
    """Map coach agent status to AgentStatus."""
    mapping = {
        "completed": AgentStatus.COMPLETED,
        "error": AgentStatus.ERROR,
    }
    return mapping.get(status, AgentStatus.COMPLETED)

