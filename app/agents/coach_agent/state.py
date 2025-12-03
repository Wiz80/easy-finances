"""
Coach Agent State.

Defines the state schema for the LangGraph coach agent.
"""

from typing import TypedDict, Annotated
from uuid import UUID

from langgraph.graph.message import add_messages


class CoachAgentState(TypedDict, total=False):
    """State for the Coach Agent."""
    
    # Request info
    request_id: str
    user_id: str
    question: str
    
    # Messages (for LLM conversation)
    messages: Annotated[list, add_messages]
    
    # SQL generation
    generated_sql: str | None
    sql_confidence: float
    similar_questions: list[str]
    
    # Query execution
    query_results: list[dict] | None
    row_count: int
    columns: list[str]
    
    # Response
    response: str | None
    
    # Status
    status: str  # pending, generating_sql, executing, analyzing, completed, error
    errors: list[str]

