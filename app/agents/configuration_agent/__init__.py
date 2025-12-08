"""
Configuration Agent - Conversational user configuration via WhatsApp.

This agent handles:
- User onboarding (name, currency, timezone)
- Trip configuration (name, dates, destination)
- Budget setup (allocations by category)
- Card/Account registration

The agent uses LLM to understand natural language and guide users
through configuration flows conversationally.

Usage:
    from app.agents.configuration_agent import process_message
    
    result = await process_message(
        user_id=user.id,
        phone_number="+573115084628",
        message_body="Hola, quiero configurar un viaje",
        db=session,
    )
    
    print(result.response_text)  # Response to send to user
"""

from app.agents.configuration_agent.agent import (
    ConfigurationAgentResult,
    process_message,
)
from app.agents.configuration_agent.state import (
    ConfigurationAgentState,
    FlowType,
    create_initial_state,
)

__all__ = [
    "process_message",
    "ConfigurationAgentResult",
    "ConfigurationAgentState",
    "FlowType",
    "create_initial_state",
]

