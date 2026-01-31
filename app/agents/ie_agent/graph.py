"""
IE Agent Graph Definition using LangGraph v1.x.

Defines the state machine graph for expense extraction processing.
Based on: https://docs.langchain.com/oss/python/langgraph/overview

Graph Flow:
    START
      │
      ▼
    router ──────────────────────────────┐
      │                                  │
      ├─── text ───▶ extract_text ───────┤
      │                                  │
      ├─── audio ──▶ extract_audio ──────┤
      │                                  │
      ├─── image ──▶ extract_image ──────┤
      │                                  │
      └─── error ──▶ error_node ─────────┼───▶ finalize ──▶ END
                                         │         ▲
                                         ▼         │
                                    validate ──────┤
                                         │         │
                                         ├─ pass ─▶ lookup_fx_rate ─▶ store_expense ─┘
                                         │
                                         └─ fail ──────────────────┘
"""

from langgraph.graph import END, START, StateGraph

from app.agents.ie_agent.nodes import (
    error_node,
    extract_audio_node,
    extract_image_node,
    extract_text_node,
    finalize_node,
    get_extraction_route,
    get_storage_route,
    lookup_fx_rate_node,
    router_node,
    store_expense_node,
    validate_extraction_node,
)
from app.agents.ie_agent.state import IEAgentState
from app.logging_config import get_logger

logger = get_logger(__name__)


def build_ie_agent_graph() -> StateGraph:
    """
    Build the IE Agent state graph.
    
    Returns:
        Compiled StateGraph ready for execution
        
    Example:
        >>> graph = build_ie_agent_graph()
        >>> result = graph.invoke(initial_state)
    """
    logger.debug("building_ie_agent_graph")
    
    # Create the graph with our state schema
    graph = StateGraph(IEAgentState)
    
    # =========================================================================
    # Add Nodes
    # =========================================================================
    
    # Router node - entry point, detects input type
    graph.add_node("router", router_node)
    
    # Extraction nodes - one per input type
    graph.add_node("extract_text", extract_text_node)
    graph.add_node("extract_audio", extract_audio_node)
    graph.add_node("extract_image", extract_image_node)
    graph.add_node("error", error_node)
    
    # Validation node - checks extracted data
    graph.add_node("validate", validate_extraction_node)
    
    # FX conversion node - gets exchange rate if currencies differ
    graph.add_node("lookup_fx_rate", lookup_fx_rate_node)
    
    # Storage node - persists to database
    graph.add_node("store_expense", store_expense_node)
    
    # Finalize node - sets final status
    graph.add_node("finalize", finalize_node)
    
    # =========================================================================
    # Add Edges
    # =========================================================================
    
    # START -> router
    graph.add_edge(START, "router")
    
    # router -> conditional routing to extraction nodes
    graph.add_conditional_edges(
        "router",
        get_extraction_route,
        {
            "extract_text": "extract_text",
            "extract_audio": "extract_audio",
            "extract_image": "extract_image",
            "error": "error",
        }
    )
    
    # All extraction nodes -> validate
    graph.add_edge("extract_text", "validate")
    graph.add_edge("extract_audio", "validate")
    graph.add_edge("extract_image", "validate")
    
    # error node -> finalize (skip storage)
    graph.add_edge("error", "finalize")
    
    # validate -> conditional routing to FX lookup or finalize
    graph.add_conditional_edges(
        "validate",
        get_storage_route,
        {
            "store_expense": "lookup_fx_rate",  # Route to FX lookup first
            "end": "finalize",
        }
    )
    
    # lookup_fx_rate -> store_expense (always proceed after FX lookup)
    graph.add_edge("lookup_fx_rate", "store_expense")
    
    # store_expense -> finalize
    graph.add_edge("store_expense", "finalize")
    
    # finalize -> END
    graph.add_edge("finalize", END)
    
    logger.debug("ie_agent_graph_built")
    
    return graph


def compile_ie_agent_graph():
    """
    Build and compile the IE Agent graph.
    
    Returns:
        Compiled graph ready for invocation
        
    Example:
        >>> agent = compile_ie_agent_graph()
        >>> result = agent.invoke(state)
    """
    graph = build_ie_agent_graph()
    return graph.compile()


# Pre-compiled graph instance for reuse
_compiled_graph = None


def get_ie_agent_graph():
    """
    Get the compiled IE Agent graph (singleton pattern).
    
    Returns cached compiled graph for performance.
    
    Returns:
        Compiled graph
    """
    global _compiled_graph
    
    if _compiled_graph is None:
        logger.info("compiling_ie_agent_graph")
        _compiled_graph = compile_ie_agent_graph()
        logger.info("ie_agent_graph_compiled")
    
    return _compiled_graph

