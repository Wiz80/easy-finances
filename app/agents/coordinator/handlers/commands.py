"""
Handler for Coordinator Commands.

Processes special commands like cancel, menu, help, status.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.common.response import (
    AgentResponse,
    AgentStatus,
)
from app.logging_config import get_logger
from app.prompts.coordinator import (
    CANCEL_RESPONSE,
    MENU_RESPONSE,
    HELP_RESPONSE,
    build_status_response,
    FALLBACK_RESPONSE,
)

logger = get_logger(__name__)


async def handle_coordinator_command(
    command_action: str,
    user_id: UUID,
    user_name: str | None,
    home_currency: str | None,
    timezone: str | None,
    active_trip_name: str | None,
    budget_status: str | None,
    active_agent: str | None,
    conversation_id: UUID | None,
    db: Session,
    request_id: str,
) -> AgentResponse:
    """
    Handle special coordinator commands.
    
    Commands:
    - cancel_current_flow: Cancel current operation
    - show_menu: Show main menu
    - show_help: Show help information
    - show_status: Show current status
    - restart_conversation: Restart conversation
    - admin_reset: Admin reset
    
    Args:
        command_action: Action to perform
        user_id: User UUID
        user_name: User's name
        home_currency: User's currency
        timezone: User's timezone
        active_trip_name: Name of active trip
        budget_status: Budget status summary
        active_agent: Currently active agent
        conversation_id: Active conversation ID
        db: Database session
        request_id: Request ID for tracing
        
    Returns:
        AgentResponse with command result
    """
    logger.debug(
        "command_handler_start",
        request_id=request_id,
        command=command_action,
    )
    
    # Route to appropriate command handler
    handlers = {
        "cancel_current_flow": _handle_cancel,
        "show_menu": _handle_menu,
        "show_help": _handle_help,
        "show_status": _handle_status,
        "restart_conversation": _handle_restart,
        "admin_reset": _handle_admin_reset,
    }
    
    handler = handlers.get(command_action, _handle_unknown)
    
    response = await handler(
        user_id=user_id,
        user_name=user_name,
        home_currency=home_currency,
        timezone=timezone,
        active_trip_name=active_trip_name,
        budget_status=budget_status,
        active_agent=active_agent,
        conversation_id=conversation_id,
        db=db,
        request_id=request_id,
    )
    
    logger.debug(
        "command_handler_complete",
        request_id=request_id,
        command=command_action,
    )
    
    return response


async def _handle_cancel(
    user_id: UUID,
    conversation_id: UUID | None,
    db: Session,
    request_id: str,
    **kwargs,
) -> AgentResponse:
    """Handle cancel command."""
    # Cancel any active conversation
    if conversation_id:
        from app.storage.conversation_manager import cancel_conversation
        cancel_conversation(db, conversation_id)
    
    return AgentResponse(
        response_text=CANCEL_RESPONSE,
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=request_id,
        release_lock=True,
        continue_flow=False,
        # Clear handoff context
        handoff_context=None,
    )


async def _handle_menu(**kwargs) -> AgentResponse:
    """Handle menu command."""
    return AgentResponse(
        response_text=MENU_RESPONSE,
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=kwargs.get("request_id"),
        release_lock=True,
        continue_flow=False,
    )


async def _handle_help(**kwargs) -> AgentResponse:
    """Handle help command."""
    return AgentResponse(
        response_text=HELP_RESPONSE,
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=kwargs.get("request_id"),
        release_lock=True,
        continue_flow=False,
    )


async def _handle_status(
    user_name: str | None,
    home_currency: str | None,
    timezone: str | None,
    active_trip_name: str | None,
    budget_status: str | None,
    active_agent: str | None,
    request_id: str,
    **kwargs,
) -> AgentResponse:
    """Handle status command."""
    response_text = build_status_response(
        user_name=user_name or "Usuario",
        home_currency=home_currency or "No configurada",
        timezone=timezone or "No configurada",
        active_trip=active_trip_name,
        budget_status=budget_status,
        active_agent=active_agent,
    )
    
    return AgentResponse(
        response_text=response_text,
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=request_id,
        release_lock=True,
        continue_flow=False,
    )


async def _handle_restart(
    user_id: UUID,
    conversation_id: UUID | None,
    db: Session,
    request_id: str,
    **kwargs,
) -> AgentResponse:
    """Handle restart command."""
    # Cancel any active conversation
    if conversation_id:
        from app.storage.conversation_manager import cancel_conversation
        cancel_conversation(db, conversation_id)
    
    return AgentResponse(
        response_text="🔄 Conversación reiniciada.\n\n¿En qué puedo ayudarte?",
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=request_id,
        release_lock=True,
        continue_flow=False,
    )


async def _handle_admin_reset(
    user_id: UUID,
    conversation_id: UUID | None,
    db: Session,
    request_id: str,
    **kwargs,
) -> AgentResponse:
    """Handle admin reset command (full reset)."""
    # Cancel conversation
    if conversation_id:
        from app.storage.conversation_manager import cancel_conversation
        cancel_conversation(db, conversation_id)
    
    return AgentResponse(
        response_text="🔧 Reset administrativo completado.\n\n¿En qué puedo ayudarte?",
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=request_id,
        release_lock=True,
        continue_flow=False,
    )


async def _handle_unknown(request_id: str, **kwargs) -> AgentResponse:
    """Handle unknown command."""
    return AgentResponse(
        response_text=FALLBACK_RESPONSE,
        status=AgentStatus.COMPLETED,
        agent_name="coordinator",
        request_id=request_id,
        release_lock=True,
        continue_flow=False,
    )

