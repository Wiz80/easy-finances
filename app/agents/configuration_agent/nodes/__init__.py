"""
Configuration Agent nodes for LangGraph.

Nodes:
- load_context: Load user and conversation context from DB
- detect_intent: Use LLM to detect intent and extract entities
- process_flow: Process the current flow based on intent
- generate_response: Generate conversational response
- persist_changes: Persist any changes to the database
"""

from app.agents.configuration_agent.nodes.context import load_context_node
from app.agents.configuration_agent.nodes.intent import detect_intent_node
from app.agents.configuration_agent.nodes.processor import process_flow_node
from app.agents.configuration_agent.nodes.response import generate_response_node
from app.agents.configuration_agent.nodes.persistence import persist_changes_node

__all__ = [
    "load_context_node",
    "detect_intent_node",
    "process_flow_node",
    "generate_response_node",
    "persist_changes_node",
]

