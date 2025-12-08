"""
Handoff Protocol for Inter-Agent Communication.

This module defines the protocol for transferring conversations between agents.
A handoff occurs when:
- An agent detects the user wants something outside its domain
- An agent completes its task and the user should return to routing
- An agent explicitly transfers to a specific agent

The protocol ensures:
- Context is preserved across agent transitions
- The Coordinator knows where to route next
- Loops and infinite handoffs are prevented
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HandoffTarget(str, Enum):
    """Valid targets for handoff."""
    
    COORDINATOR = "coordinator"     # Return to Coordinator for re-routing
    CONFIGURATION = "configuration" # Configuration Agent
    IE = "ie"                       # Information Extraction Agent
    COACH = "coach"                 # Coach Agent


class HandoffReason(str, Enum):
    """Common reasons for handoff."""
    
    # From any agent back to Coordinator
    TASK_COMPLETED = "task_completed"
    USER_CANCELLED = "user_cancelled"
    SESSION_EXPIRED = "session_expired"
    INTENT_CHANGED = "intent_changed"
    
    # To Configuration Agent
    NEEDS_ONBOARDING = "needs_onboarding"
    NEEDS_TRIP_SETUP = "needs_trip_setup"
    NEEDS_CARD_SETUP = "needs_card_setup"
    NEEDS_BUDGET_CONFIG = "needs_budget_config"
    
    # To IE Agent
    EXPENSE_DETECTED = "expense_detected"
    RECEIPT_UPLOADED = "receipt_uploaded"
    VOICE_EXPENSE = "voice_expense"
    
    # To Coach Agent
    QUERY_DETECTED = "query_detected"
    REPORT_REQUESTED = "report_requested"
    BUDGET_QUESTION = "budget_question"


@dataclass
class HandoffSignal:
    """
    Signal from an agent requesting a handoff.
    
    This object is created by an agent when it determines the conversation
    should be handled by a different agent.
    
    Attributes:
        target: Which agent should receive the conversation
        reason: Why the handoff is happening
        context: Data to pass to the target agent
        original_message: The user message that triggered the handoff
        preserve_flow: Whether the target should continue the current flow
        
    Example:
        >>> # Coach Agent detects user wants to log expense
        >>> HandoffSignal(
        ...     target=HandoffTarget.IE,
        ...     reason=HandoffReason.EXPENSE_DETECTED,
        ...     context={"raw_input": "50 soles en taxi"},
        ...     original_message="Acabo de gastar 50 soles en taxi",
        ... )
    """
    
    target: HandoffTarget
    reason: HandoffReason | str
    context: dict[str, Any] = field(default_factory=dict)
    original_message: str | None = None
    preserve_flow: bool = False
    
    # Metadata
    source_agent: str | None = None
    confidence: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage/logging."""
        return {
            "target": self.target.value if isinstance(self.target, HandoffTarget) else self.target,
            "reason": self.reason.value if isinstance(self.reason, HandoffReason) else self.reason,
            "context": self.context,
            "original_message": self.original_message,
            "preserve_flow": self.preserve_flow,
            "source_agent": self.source_agent,
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffSignal":
        """Create from dictionary."""
        target = data.get("target", "coordinator")
        if isinstance(target, str):
            try:
                target = HandoffTarget(target)
            except ValueError:
                target = HandoffTarget.COORDINATOR
        
        reason = data.get("reason", "unknown")
        if isinstance(reason, str):
            try:
                reason = HandoffReason(reason)
            except ValueError:
                pass  # Keep as string if not a known reason
        
        return cls(
            target=target,
            reason=reason,
            context=data.get("context", {}),
            original_message=data.get("original_message"),
            preserve_flow=data.get("preserve_flow", False),
            source_agent=data.get("source_agent"),
            confidence=data.get("confidence", 1.0),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory functions for common handoff patterns
# ─────────────────────────────────────────────────────────────────────────────

def handoff_to_coordinator(
    reason: HandoffReason | str = HandoffReason.TASK_COMPLETED,
    source_agent: str | None = None,
) -> HandoffSignal:
    """Create a handoff back to the Coordinator."""
    return HandoffSignal(
        target=HandoffTarget.COORDINATOR,
        reason=reason,
        source_agent=source_agent,
    )


def handoff_to_ie(
    raw_input: str,
    source_agent: str,
    reason: HandoffReason = HandoffReason.EXPENSE_DETECTED,
) -> HandoffSignal:
    """Create a handoff to the IE Agent for expense processing."""
    return HandoffSignal(
        target=HandoffTarget.IE,
        reason=reason,
        context={"raw_input": raw_input},
        original_message=raw_input,
        source_agent=source_agent,
    )


def handoff_to_coach(
    question: str,
    source_agent: str,
    reason: HandoffReason = HandoffReason.QUERY_DETECTED,
) -> HandoffSignal:
    """Create a handoff to the Coach Agent for query processing."""
    return HandoffSignal(
        target=HandoffTarget.COACH,
        reason=reason,
        context={"question": question},
        original_message=question,
        source_agent=source_agent,
    )


def handoff_to_configuration(
    flow: str,
    source_agent: str,
    reason: HandoffReason = HandoffReason.NEEDS_TRIP_SETUP,
    context: dict[str, Any] | None = None,
) -> HandoffSignal:
    """Create a handoff to the Configuration Agent."""
    return HandoffSignal(
        target=HandoffTarget.CONFIGURATION,
        reason=reason,
        context={"target_flow": flow, **(context or {})},
        source_agent=source_agent,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handoff validation and safety
# ─────────────────────────────────────────────────────────────────────────────

MAX_HANDOFFS_PER_MESSAGE = 3  # Prevent infinite loops


def validate_handoff(
    signal: HandoffSignal,
    handoff_count: int,
) -> tuple[bool, str | None]:
    """
    Validate a handoff signal.
    
    Args:
        signal: The handoff signal to validate
        handoff_count: Number of handoffs already performed this message
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for too many handoffs (loop prevention)
    if handoff_count >= MAX_HANDOFFS_PER_MESSAGE:
        return False, f"Max handoffs ({MAX_HANDOFFS_PER_MESSAGE}) exceeded"
    
    # Check for self-handoff
    if signal.source_agent and signal.target.value == signal.source_agent:
        return False, f"Agent {signal.source_agent} cannot hand off to itself"
    
    return True, None

