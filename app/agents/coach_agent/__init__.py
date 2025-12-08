"""
Coach Agent Package.

Financial coach agent for natural language queries about user finances.

Components:
- agent.py: Main entry point (ask_coach function)
- graph.py: LangGraph definition
- state.py: Agent state schema
- tools/: LangChain tools (generate_sql, run_sql, etc.)
- services/: Internal services (Vanna, Database, Validator)
"""

from app.agents.coach_agent.agent import (
    ask_coach,
    CoachAgentResult,
    get_graph,
    reset_graph,
)

__all__ = [
    "ask_coach",
    "CoachAgentResult",
    "get_graph",
    "reset_graph",
]
