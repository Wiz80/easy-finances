"""
Handler for IVR (menu-based) flows.

Handles onboarding, budget creation, trip creation, and card configuration
without using LLM - uses deterministic menu-based flows instead.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.common.response import (
    AgentResponse,
    AgentStatus,
    error_response,
)
from app.flows.ivr_processor import IVRProcessor, IVRResponse
from app.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


async def handle_ivr_onboarding(
    user: User,
    message_body: str,
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Handle IVR onboarding flow.
    
    This replaces the Configuration Agent for initial user setup,
    using deterministic menu-based flows instead of LLM.
    
    Args:
        user: User model instance
        message_body: User's message
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with onboarding result
    """
    try:
        logger.debug(
            "ivr_onboarding_start",
            request_id=request_id,
            user_id=str(user.id),
            current_step=user.onboarding_step,
        )
        
        processor = IVRProcessor(db)
        
        # Process onboarding step
        result = processor.process_onboarding(
            user=user,
            current_step=user.onboarding_step,
            user_input=message_body,
        )
        
        # Convert IVRResponse to AgentResponse
        response = _ivr_to_agent_response(
            ivr_response=result,
            agent_name="ivr_onboarding",
            flow_name="onboarding",
            request_id=request_id,
        )
        
        logger.debug(
            "ivr_onboarding_complete",
            request_id=request_id,
            next_step=result.next_step,
            flow_complete=result.flow_complete,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "ivr_onboarding_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error en el proceso de configuración. Por favor intenta de nuevo.",
            agent_name="ivr_onboarding",
            errors=[str(e)],
            request_id=request_id,
        )


async def handle_ivr_budget_creation(
    user: User,
    message_body: str,
    current_step: str | None,
    flow_data: dict[str, Any],
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Handle IVR budget creation flow.
    
    Args:
        user: User model instance
        message_body: User's message
        current_step: Current step in budget flow
        flow_data: Accumulated flow data
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with budget creation result
    """
    try:
        logger.debug(
            "ivr_budget_start",
            request_id=request_id,
            user_id=str(user.id),
            current_step=current_step,
        )
        
        processor = IVRProcessor(db)
        
        # Process budget creation step
        result = processor.process_budget_creation(
            user=user,
            current_step=current_step,
            user_input=message_body,
            temp_data=flow_data,
        )
        
        # Convert IVRResponse to AgentResponse
        response = _ivr_to_agent_response(
            ivr_response=result,
            agent_name="ivr_budget",
            flow_name="budget_creation",
            request_id=request_id,
            flow_data=flow_data,
        )
        
        logger.debug(
            "ivr_budget_complete",
            request_id=request_id,
            next_step=result.next_step,
            flow_complete=result.flow_complete,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "ivr_budget_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error al crear el presupuesto. Por favor intenta de nuevo.",
            agent_name="ivr_budget",
            errors=[str(e)],
            request_id=request_id,
        )


async def handle_ivr_trip_creation(
    user: User,
    message_body: str,
    current_step: str | None,
    flow_data: dict[str, Any],
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Handle IVR trip creation flow.
    
    Args:
        user: User model instance
        message_body: User's message
        current_step: Current step in trip flow
        flow_data: Accumulated flow data
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with trip creation result
    """
    try:
        logger.debug(
            "ivr_trip_start",
            request_id=request_id,
            user_id=str(user.id),
            current_step=current_step,
        )
        
        processor = IVRProcessor(db)
        
        # Process trip creation step
        result = processor.process_trip_creation(
            user=user,
            current_step=current_step,
            user_input=message_body,
            temp_data=flow_data,
        )
        
        # Convert IVRResponse to AgentResponse
        response = _ivr_to_agent_response(
            ivr_response=result,
            agent_name="ivr_trip",
            flow_name="trip_creation",
            request_id=request_id,
            flow_data=flow_data,
        )
        
        logger.debug(
            "ivr_trip_complete",
            request_id=request_id,
            next_step=result.next_step,
            flow_complete=result.flow_complete,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "ivr_trip_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error al configurar el viaje. Por favor intenta de nuevo.",
            agent_name="ivr_trip",
            errors=[str(e)],
            request_id=request_id,
        )


async def handle_ivr_card_configuration(
    user: User,
    message_body: str,
    current_step: str | None,
    flow_data: dict[str, Any],
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Handle IVR card configuration flow.
    
    Args:
        user: User model instance
        message_body: User's message
        current_step: Current step in card flow
        flow_data: Accumulated flow data
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with card configuration result
    """
    try:
        logger.debug(
            "ivr_card_start",
            request_id=request_id,
            user_id=str(user.id),
            current_step=current_step,
        )
        
        processor = IVRProcessor(db)
        
        # Process card configuration step
        result = processor.process_card_configuration(
            user=user,
            current_step=current_step,
            user_input=message_body,
            temp_data=flow_data,
        )
        
        # Convert IVRResponse to AgentResponse
        response = _ivr_to_agent_response(
            ivr_response=result,
            agent_name="ivr_card",
            flow_name="card_configuration",
            request_id=request_id,
            flow_data=flow_data,
        )
        
        logger.debug(
            "ivr_card_complete",
            request_id=request_id,
            next_step=result.next_step,
            flow_complete=result.flow_complete,
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "ivr_card_error",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        return error_response(
            text="⚠️ Error al configurar la tarjeta. Por favor intenta de nuevo.",
            agent_name="ivr_card",
            errors=[str(e)],
            request_id=request_id,
        )


def _ivr_to_agent_response(
    ivr_response: IVRResponse,
    agent_name: str,
    flow_name: str,
    request_id: str,
    flow_data: dict[str, Any] | None = None,
) -> AgentResponse:
    """
    Convert IVRResponse to AgentResponse.
    
    Args:
        ivr_response: Response from IVR processor
        agent_name: Name of the agent for logging
        flow_name: Name of the flow (onboarding, budget, trip, card)
        request_id: Request ID for tracing
        flow_data: Accumulated flow data to include
        
    Returns:
        AgentResponse compatible with coordinator
    """
    # Determine status
    if ivr_response.flow_complete:
        status = AgentStatus.COMPLETED
        release_lock = True
    elif ivr_response.error:
        status = AgentStatus.AWAITING_INPUT
        release_lock = False
    else:
        status = AgentStatus.AWAITING_INPUT
        release_lock = False
    
    # Merge flow data
    merged_data = flow_data.copy() if flow_data else {}
    if ivr_response.data:
        merged_data.update(ivr_response.data)
    
    return AgentResponse(
        response_text=ivr_response.message,
        status=status,
        agent_name=agent_name,
        request_id=request_id,
        release_lock=release_lock,
        handoff_to=None,
        handoff_context=None,
        current_flow=flow_name,
        current_step=ivr_response.next_step,
        pending_field=ivr_response.next_step,
        flow_data=merged_data,
        errors=[ivr_response.error] if ivr_response.error else [],
        conversation_persisted=False,  # IVR doesn't persist directly
        conversation_id=None,
    )

