"""
Configuration Agent - Conversational user configuration via WhatsApp.

.. deprecated::
    This agent is deprecated as of Phase 5 of the budget refactoring plan.
    Use ``app.flows.ivr_processor.IVRProcessor`` instead for:
    - User onboarding
    - Trip configuration
    - Budget setup
    - Card/Account registration
    
    The IVR-based flows provide a simpler, more reliable experience
    without requiring LLM calls for configuration steps.

This agent handles:
- User onboarding (name, currency, timezone)
- Trip configuration (name, dates, destination)
- Budget setup (allocations by category)
- Card/Account registration

The agent uses LLM to understand natural language and guide users
through configuration flows conversationally.

Usage (DEPRECATED):
    from app.agents.configuration_agent import process_message
    
    result = await process_message(
        user_id=user.id,
        phone_number="+573115084628",
        message_body="Hola, quiero configurar un viaje",
        db=session,
    )
    
    print(result.response_text)  # Response to send to user

RECOMMENDED - Use IVRProcessor instead:
    from app.flows.ivr_processor import IVRProcessor
    
    processor = IVRProcessor(db=session)
    response = processor.process_onboarding(user, "name", "Juan")
"""

import warnings

# Emit deprecation warning when module is imported
warnings.warn(
    "configuration_agent is deprecated. "
    "Use app.flows.ivr_processor.IVRProcessor for onboarding, "
    "budget, trip, and card configuration flows instead.",
    DeprecationWarning,
    stacklevel=2
)

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

