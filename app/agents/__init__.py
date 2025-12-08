"""
Agents module.

Contains LangGraph-based agents for the personal finance assistant.

Available agents:
- Coordinator Agent: Multi-agent router and orchestrator (entry point)
- Configuration Agent: Conversational user configuration via WhatsApp
- IE Agent: Information Extraction from text, audio, and images
- Coach Agent: Analytics and insights using SQL + RAG

Common infrastructure:
- AgentResponse: Unified response format for all agents
- HandoffSignal: Inter-agent communication protocol
- AgentType: Agent type enumeration for routing

Usage:
    # Recommended: Use Coordinator as entry point
    from app.agents.coordinator import process_message
    
    result = await process_message(
        phone_number="+573115084628",
        message_body="Gasté 50 soles en taxi",
    )
"""

from app.agents.ie_agent import (
    IEAgentResult,
    process_expense,
)
from app.agents.configuration_agent import (
    ConfigurationAgentResult,
    process_message as process_config_message,
)
from app.agents.coordinator import (
    CoordinatorResult,
    process_message,
    handle_whatsapp_message,
)
from app.agents.common import (
    AgentResponse,
    AgentStatus,
    AgentType,
    HandoffSignal,
    HandoffTarget,
)

__all__ = [
    # Coordinator Agent (main entry point)
    "process_message",
    "handle_whatsapp_message",
    "CoordinatorResult",
    # IE Agent
    "process_expense",
    "IEAgentResult",
    # Configuration Agent
    "process_config_message",
    "ConfigurationAgentResult",
    # Common infrastructure
    "AgentResponse",
    "AgentStatus",
    "AgentType",
    "HandoffSignal",
    "HandoffTarget",
]

