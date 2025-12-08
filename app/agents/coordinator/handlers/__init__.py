"""
Agent Handlers for the Coordinator.

Each handler wraps a specialized agent and converts its response
to the unified AgentResponse format.
"""

from app.agents.coordinator.handlers.configuration import handle_configuration_agent
from app.agents.coordinator.handlers.ie import handle_ie_agent
from app.agents.coordinator.handlers.coach import handle_coach_agent
from app.agents.coordinator.handlers.commands import handle_coordinator_command

__all__ = [
    "handle_configuration_agent",
    "handle_ie_agent",
    "handle_coach_agent",
    "handle_coordinator_command",
]

