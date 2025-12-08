"""
Coach Agent Tools.

LangChain tools for the financial coach agent.
"""

from app.agents.coach_agent.tools.generate_sql import generate_sql
from app.agents.coach_agent.tools.run_sql import run_sql_query
from app.agents.coach_agent.tools.validate_sql import validate_sql
from app.agents.coach_agent.tools.date_utils import get_current_date


def get_coach_tools():
    """Get all tools for the coach agent."""
    return [
        generate_sql,
        run_sql_query,
        validate_sql,
        get_current_date,
    ]


__all__ = [
    "generate_sql",
    "run_sql_query",
    "validate_sql",
    "get_current_date",
    "get_coach_tools",
]

