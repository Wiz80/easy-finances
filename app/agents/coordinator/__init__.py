"""
Coordinator Agent - Multi-Agent Router.

The Coordinator Agent is the entry point for all WhatsApp messages.
It determines which specialized agent should handle each message:
- ConfigurationAgent: User setup, trips, cards, budgets
- IEAgent: Expense extraction and storage
- CoachAgent: Financial queries and reports

Key features:
- Intent detection (hybrid: keywords + LLM)
- Sticky sessions: Keep user with same agent during a flow
- Handoff protocol: Agents can transfer conversations
- Special commands: cancel, menu, help

Usage:
    from app.agents.coordinator import process_message
    
    response = await process_message(
        phone_number="+573115084628",
        message_body="Gasté 50 soles en taxi",
    )
    
    # response.response_text contains the reply to send
    # response.agent_used shows which agent handled it
"""

from app.agents.coordinator.router import (
    IntentRouter,
    RoutingResult,
    IntentChangeResult,
    detect_agent_for_message,
    detect_intent_change,
)
from app.agents.coordinator.agent import (
    CoordinatorResult,
    process_message,
    handle_whatsapp_message,
)
from app.agents.coordinator.state import (
    CoordinatorState,
    create_initial_state,
)
from app.agents.coordinator.graph import (
    get_coordinator_graph,
    reset_graph,
)

__all__ = [
    # Agent Entry Point
    "process_message",
    "handle_whatsapp_message",
    "CoordinatorResult",
    # Router
    "IntentRouter",
    "RoutingResult",
    "IntentChangeResult",
    "detect_agent_for_message",
    "detect_intent_change",
    # State
    "CoordinatorState",
    "create_initial_state",
    # Graph
    "get_coordinator_graph",
    "reset_graph",
]

