"""
Configuration Agent Graph Definition using LangGraph.

Defines the state machine graph for conversational configuration flows.

Graph Flow:
    START
      │
      ▼
    load_context ─────────────────────────────────────┐
      │                                               │
      ▼                                               │
    detect_intent ────────────────────────────────────┤
      │                                               │
      ▼                                               │
    process_flow ─────────────────────────────────────┤
      │                                               │
      ▼                                               │
    generate_response ────────────────────────────────┤
      │                                               │
      ▼                                               │
    persist_changes ──────────────────────────────────┘
      │
      ▼
     END
"""

from typing import Callable

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.configuration_agent.nodes import (
    detect_intent_node,
    generate_response_node,
    load_context_node,
    persist_changes_node,
    process_flow_node,
)
from app.agents.configuration_agent.state import ConfigurationAgentState
from app.logging_config import get_logger

logger = get_logger(__name__)


def build_configuration_agent_graph(db: Session) -> StateGraph:
    """
    Build the Configuration Agent state graph.
    
    Args:
        db: Database session to inject into nodes that need it
        
    Returns:
        StateGraph ready for compilation
    """
    logger.debug("building_configuration_agent_graph")
    
    # Create the graph with our state schema
    graph = StateGraph(ConfigurationAgentState)
    
    # =========================================================================
    # Create node wrappers that inject the database session
    # =========================================================================
    
    def load_context(state: ConfigurationAgentState) -> ConfigurationAgentState:
        return load_context_node(state, db=db)
    
    def persist_changes(state: ConfigurationAgentState) -> ConfigurationAgentState:
        return persist_changes_node(state, db=db)
    
    # =========================================================================
    # Add Nodes
    # =========================================================================
    
    # Load user and conversation context from DB
    graph.add_node("load_context", load_context)
    
    # Detect intent using LLM
    graph.add_node("detect_intent", detect_intent_node)
    
    # Process the flow based on intent
    graph.add_node("process_flow", process_flow_node)
    
    # Generate natural language response
    graph.add_node("generate_response", generate_response_node)
    
    # Persist changes to database
    graph.add_node("persist_changes", persist_changes)
    
    # =========================================================================
    # Add Edges (Linear flow for now)
    # =========================================================================
    
    # START -> load_context
    graph.add_edge(START, "load_context")
    
    # load_context -> detect_intent (or error)
    graph.add_conditional_edges(
        "load_context",
        _route_after_context,
        {
            "detect_intent": "detect_intent",
            "error": "generate_response",  # Skip to response if error
        }
    )
    
    # detect_intent -> process_flow
    graph.add_edge("detect_intent", "process_flow")
    
    # process_flow -> generate_response
    graph.add_edge("process_flow", "generate_response")
    
    # generate_response -> persist_changes
    graph.add_edge("generate_response", "persist_changes")
    
    # persist_changes -> END
    graph.add_edge("persist_changes", END)
    
    logger.debug("configuration_agent_graph_built")
    
    return graph


def _route_after_context(state: ConfigurationAgentState) -> str:
    """Route after loading context - check for errors."""
    if state.get("status") == "error":
        return "error"
    return "detect_intent"


def compile_configuration_agent_graph(db: Session):
    """
    Build and compile the Configuration Agent graph.
    
    Args:
        db: Database session
        
    Returns:
        Compiled graph ready for invocation
    """
    graph = build_configuration_agent_graph(db)
    return graph.compile()

