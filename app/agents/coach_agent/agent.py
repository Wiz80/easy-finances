"""
Coach Agent Entry Point.

Main interface for interacting with the financial coach agent.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from app.agents.coach_agent.graph import create_coach_graph

logger = structlog.get_logger(__name__)


@dataclass
class CoachAgentResult:
    """Result from the Coach Agent."""
    
    request_id: str
    user_id: str
    question: str
    response: str
    sql_executed: str | None = None
    data_summary: dict[str, Any] | None = None
    status: str = "completed"
    errors: list[str] = field(default_factory=list)


# Cache for compiled graph
_compiled_graph = None


async def get_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = await create_coach_graph()
    return _compiled_graph


async def ask_coach(
    user_id: str,
    question: str,
    request_id: str | None = None,
) -> CoachAgentResult:
    """
    Ask the financial coach a question.
    
    The coach will:
    1. Analyze the question
    2. Generate SQL using the MCP server
    3. Execute the query
    4. Analyze results and provide a human-friendly response
    
    Args:
        user_id: User ID (UUID) for data isolation
        question: Natural language question about finances
        request_id: Optional request ID for tracing
        
    Returns:
        CoachAgentResult with the response and metadata
        
    Example:
        >>> result = await ask_coach(
        ...     user_id="abc-123",
        ...     question="¿Cuánto gasté en comida este mes?"
        ... )
        >>> print(result.response)
        "Este mes has gastado $450.50 en comida..."
    """
    request_id = request_id or str(uuid.uuid4())
    
    log = logger.bind(
        request_id=request_id,
        user_id=user_id,
        question=question[:50],
    )
    log.info("coach_agent_request")
    
    try:
        # Get compiled graph
        graph = await get_graph()
        
        # Prepare input with user context
        input_message = f"""Usuario ID: {user_id}

Pregunta: {question}

Por favor usa las herramientas disponibles para consultar los datos financieros del usuario y responder su pregunta."""
        
        # Run the graph
        result = await graph.ainvoke({
            "messages": [HumanMessage(content=input_message)],
            "user_id": user_id,
            "question": question,
            "request_id": request_id,
        })
        
        # Extract response from messages
        messages = result.get("messages", [])
        response_text = ""
        sql_executed = None
        
        for msg in reversed(messages):
            if hasattr(msg, "content") and isinstance(msg.content, str):
                # Last AI message is the response
                if msg.type == "ai" and not hasattr(msg, "tool_calls"):
                    response_text = msg.content
                    break
            
            # Check for tool results to get SQL
            if hasattr(msg, "name") and msg.name == "generate_sql":
                import json
                try:
                    tool_result = json.loads(msg.content)
                    sql_executed = tool_result.get("sql")
                except:
                    pass
        
        log.info("coach_agent_success", response_length=len(response_text))
        
        return CoachAgentResult(
            request_id=request_id,
            user_id=user_id,
            question=question,
            response=response_text,
            sql_executed=sql_executed,
            status="completed",
        )
        
    except Exception as e:
        log.error("coach_agent_error", error=str(e))
        
        return CoachAgentResult(
            request_id=request_id,
            user_id=user_id,
            question=question,
            response=f"Lo siento, hubo un error procesando tu pregunta: {str(e)}",
            status="error",
            errors=[str(e)],
        )


# Reset graph cache (useful for testing)
def reset_graph():
    """Reset the cached graph."""
    global _compiled_graph
    _compiled_graph = None

