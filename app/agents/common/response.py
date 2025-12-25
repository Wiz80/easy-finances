"""
Unified AgentResponse for all agents.

This module defines the standard response format that all agents
(ConfigurationAgent, IEAgent, CoachAgent) must return to the Coordinator.

The AgentResponse enables:
- Consistent response handling
- Handoff signaling between agents
- Session lock management
- Context preservation across agents
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class AgentStatus(str, Enum):
    """Status of agent execution."""
    
    COMPLETED = "completed"           # Task finished successfully
    AWAITING_INPUT = "awaiting_input" # Waiting for user response
    ERROR = "error"                   # Error occurred
    HANDOFF = "handoff"               # Transferring to another agent


@dataclass
class AgentResponse:
    """
    Unified response format from any agent to the Coordinator.
    
    All agents (ConfigurationAgent, IEAgent, CoachAgent) should return
    this object so the Coordinator can:
    - Send the response to the user
    - Handle handoffs to other agents
    - Manage session locks (sticky sessions)
    - Preserve context across agent transitions
    
    Attributes:
        response_text: Text to send back to the user via WhatsApp
        status: Current status of the agent execution
        
        # Handoff signals
        handoff_to: Target agent for handoff (None = no handoff)
        handoff_reason: Why the handoff is happening
        handoff_context: Data to pass to the next agent
        
        # Session management
        release_lock: Whether to release the sticky session lock
        continue_flow: Whether to continue in the current flow
        
        # Metadata
        agent_name: Name of the agent that generated this response
        confidence: Confidence score (0.0-1.0) if applicable
        
        # Created entities (for tracking)
        created_expense_id: If an expense was created
        created_trip_id: If a trip was created
        created_budget_id: If a budget was created
        
        # Errors
        errors: List of error messages
        
    Example:
        >>> # IE Agent completes expense registration
        >>> AgentResponse(
        ...     response_text="✅ Gasto registrado: $50 USD - Taxi",
        ...     status=AgentStatus.COMPLETED,
        ...     agent_name="ie_agent",
        ...     created_expense_id=expense.id,
        ...     release_lock=True,  # Allow routing next message
        ... )
        
        >>> # Coach Agent wants to hand off to IE Agent
        >>> AgentResponse(
        ...     response_text="Entiendo, te ayudo a registrar ese gasto.",
        ...     status=AgentStatus.HANDOFF,
        ...     handoff_to="ie",
        ...     handoff_context={"raw_input": "50 soles en taxi"},
        ...     release_lock=True,
        ... )
    """
    
    # Required: Response to user
    response_text: str
    status: AgentStatus = AgentStatus.COMPLETED
    
    # Handoff signals (for inter-agent transfer)
    handoff_to: str | None = None  # "coordinator", "configuration", "ie", "coach"
    handoff_reason: str | None = None
    handoff_context: dict[str, Any] | None = None
    
    # Session management
    release_lock: bool = False  # Release sticky session?
    continue_flow: bool = True  # Continue in current flow?
    
    # Metadata
    agent_name: str = "unknown"
    confidence: float = 1.0
    request_id: str | None = None
    
    # Created entities (for tracking)
    created_expense_id: UUID | None = None
    created_trip_id: UUID | None = None
    created_budget_id: UUID | None = None
    created_card_id: UUID | None = None
    
    # Flow state (for Configuration Agent)
    current_flow: str | None = None
    current_step: str | None = None
    pending_field: str | None = None
    flow_data: dict[str, Any] = field(default_factory=dict)
    
    # Conversation tracking (for state sync)
    conversation_id: UUID | None = None
    conversation_persisted: bool = False  # True if agent already persisted conversation state
    
    # Errors
    errors: list[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Whether the agent completed successfully."""
        return self.status in (AgentStatus.COMPLETED, AgentStatus.AWAITING_INPUT)
    
    @property
    def wants_handoff(self) -> bool:
        """Whether the agent wants to hand off to another agent."""
        return self.handoff_to is not None
    
    @property
    def is_terminal(self) -> bool:
        """Whether this response ends the current agent interaction."""
        return self.release_lock or self.status == AgentStatus.ERROR
    
    def with_handoff(
        self,
        target: str,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> "AgentResponse":
        """
        Create a copy with handoff signal.
        
        Args:
            target: Target agent ("coordinator", "configuration", "ie", "coach")
            reason: Reason for handoff
            context: Context to pass to target agent
            
        Returns:
            New AgentResponse with handoff configured
        """
        return AgentResponse(
            response_text=self.response_text,
            status=AgentStatus.HANDOFF,
            handoff_to=target,
            handoff_reason=reason,
            handoff_context=context or self.handoff_context,
            release_lock=True,
            continue_flow=False,
            agent_name=self.agent_name,
            confidence=self.confidence,
            request_id=self.request_id,
            errors=self.errors,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response_text": self.response_text,
            "status": self.status.value if isinstance(self.status, AgentStatus) else self.status,
            "success": self.success,
            "agent_name": self.agent_name,
            "handoff_to": self.handoff_to,
            "handoff_reason": self.handoff_reason,
            "release_lock": self.release_lock,
            "continue_flow": self.continue_flow,
            "confidence": self.confidence,
            "errors": self.errors,
            "created_expense_id": str(self.created_expense_id) if self.created_expense_id else None,
            "created_trip_id": str(self.created_trip_id) if self.created_trip_id else None,
            "created_budget_id": str(self.created_budget_id) if self.created_budget_id else None,
        }
    
    def __repr__(self) -> str:
        return (
            f"AgentResponse(agent={self.agent_name}, status={self.status.value}, "
            f"handoff_to={self.handoff_to}, release_lock={self.release_lock})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory functions for common response patterns
# ─────────────────────────────────────────────────────────────────────────────

def success_response(
    text: str,
    agent_name: str,
    release_lock: bool = True,
    **kwargs
) -> AgentResponse:
    """Create a successful completion response."""
    return AgentResponse(
        response_text=text,
        status=AgentStatus.COMPLETED,
        agent_name=agent_name,
        release_lock=release_lock,
        **kwargs
    )


def awaiting_input_response(
    text: str,
    agent_name: str,
    pending_field: str | None = None,
    **kwargs
) -> AgentResponse:
    """Create a response awaiting user input."""
    return AgentResponse(
        response_text=text,
        status=AgentStatus.AWAITING_INPUT,
        agent_name=agent_name,
        release_lock=False,  # Keep lock while waiting
        pending_field=pending_field,
        **kwargs
    )


def error_response(
    text: str,
    agent_name: str,
    errors: list[str] | None = None,
    **kwargs
) -> AgentResponse:
    """Create an error response."""
    return AgentResponse(
        response_text=text,
        status=AgentStatus.ERROR,
        agent_name=agent_name,
        release_lock=True,  # Release lock on error
        errors=errors or [],
        **kwargs
    )


def handoff_response(
    text: str,
    agent_name: str,
    target: str,
    reason: str | None = None,
    context: dict[str, Any] | None = None,
    **kwargs
) -> AgentResponse:
    """Create a handoff response to another agent."""
    return AgentResponse(
        response_text=text,
        status=AgentStatus.HANDOFF,
        agent_name=agent_name,
        handoff_to=target,
        handoff_reason=reason,
        handoff_context=context,
        release_lock=True,
        continue_flow=False,
        **kwargs
    )

