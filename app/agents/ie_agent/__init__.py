"""
IE Agent - Information Extraction Agent.

Multi-modal expense extraction agent using LangGraph.
Processes text, audio, and image inputs to extract structured expense data.

Usage:
    from app.agents.ie_agent import process_expense
    
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input="Gasté 50 soles en taxi",
    )
    
    if result.success:
        print(f"Created expense: {result.expense_id}")
"""

from app.agents.ie_agent.agent import (
    IEAgentResult,
    process,
    process_expense,
    run,
)
from app.agents.ie_agent.graph import (
    build_ie_agent_graph,
    compile_ie_agent_graph,
    get_ie_agent_graph,
)
from app.agents.ie_agent.state import (
    AgentStatus,
    IEAgentState,
    InputType,
    create_initial_state,
)

__all__ = [
    # Main entry points
    "process_expense",
    "process",
    "run",
    "IEAgentResult",
    # State
    "IEAgentState",
    "InputType",
    "AgentStatus",
    "create_initial_state",
    # Graph
    "build_ie_agent_graph",
    "compile_ie_agent_graph",
    "get_ie_agent_graph",
]

