"""
Coach Agent Graph.

LangGraph definition for the financial coach agent.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI

from app.agents.coach_agent.state import CoachAgentState
from app.agents.coach_agent.mcp_client import get_mcp_tools
from app.prompts.coach_agent import COACH_SYSTEM_PROMPT
from app.config import settings


async def create_coach_graph():
    """
    Create the Coach Agent LangGraph.
    
    Flow:
    1. call_model: LLM decides which tool to call
    2. tools: Execute MCP tools (generate_sql, run_sql_query)
    3. call_model: LLM analyzes results and responds
    
    Returns:
        Compiled LangGraph
    """
    # Load MCP tools
    tools = await get_mcp_tools()
    
    # Initialize LLM
    model = ChatOpenAI(
        model=settings.llm_provider == "openai" and "gpt-4o" or "gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0.1,
    )
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    def call_model(state: CoachAgentState) -> dict:
        """Call the LLM with system prompt and tools."""
        messages = state.get("messages", [])
        
        # Add system prompt if not present
        if not messages or messages[0].type != "system":
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=COACH_SYSTEM_PROMPT)] + list(messages)
        
        response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    # Build graph
    builder = StateGraph(CoachAgentState)
    
    # Add nodes
    builder.add_node("call_model", call_model)
    builder.add_node("tools", ToolNode(tools))
    
    # Add edges
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,  # Routes to "tools" if tool call, END otherwise
    )
    builder.add_edge("tools", "call_model")
    
    return builder.compile()

