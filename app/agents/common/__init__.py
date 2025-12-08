"""
Common infrastructure for multi-agent coordination.

This module provides shared components for the Coordinator Agent system:
- AgentResponse: Unified response format for all agents
- Handoff protocol: Inter-agent communication and transfer
- Intent definitions: Categories and keywords for routing

Usage:
    from app.agents.common import AgentResponse, AgentType, HandoffSignal
    
    # Return unified response from any agent
    return AgentResponse(
        response_text="Gasto registrado!",
        status="completed",
        release_lock=True
    )
"""

from app.agents.common.response import AgentResponse, AgentStatus
from app.agents.common.handoff import HandoffSignal, HandoffTarget
from app.agents.common.intents import (
    AgentType,
    EXPENSE_KEYWORDS,
    QUERY_KEYWORDS,
    CONFIG_KEYWORDS,
    COORDINATOR_COMMANDS,
)

__all__ = [
    # Response
    "AgentResponse",
    "AgentStatus",
    # Handoff
    "HandoffSignal",
    "HandoffTarget",
    # Intents
    "AgentType",
    "EXPENSE_KEYWORDS",
    "QUERY_KEYWORDS",
    "CONFIG_KEYWORDS",
    "COORDINATOR_COMMANDS",
]

