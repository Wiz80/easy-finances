"""
Coach Agent.

LangGraph agent that answers financial questions by connecting
to the Finanzas MCP Server for NL-to-SQL and query execution.

Uses langchain-mcp-adapters to load MCP tools.

Usage:
    from app.agents.coach_agent import ask_coach
    
    result = await ask_coach(
        user_id="...",
        question="¿Cuánto gasté este mes?"
    )
"""

from app.agents.coach_agent.agent import ask_coach, CoachAgentResult

__all__ = ["ask_coach", "CoachAgentResult"]

