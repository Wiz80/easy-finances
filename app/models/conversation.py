"""Conversation state model for multi-turn chat interactions."""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Default conversation timeout in minutes
DEFAULT_CONVERSATION_TIMEOUT_MINUTES = 30


class ConversationState(Base):
    """
    Tracks conversation state for multi-turn WhatsApp interactions.
    
    Essential for the Coordinator Agent to maintain context across messages
    and route to the appropriate specialized agent.
    
    Each user can have one active conversation at a time.
    
    Flows:
    - onboarding: New user setup (name, currency, timezone)
    - trip_setup: Configure a new trip
    - card_setup: Register a new card/account
    - budget_config: Create/edit budget allocations
    - expense: Log an expense (handed to IE Agent)
    - query: Ask questions (handed to Coach Agent)
    
    Agent Routing:
    The Coordinator uses active_agent and agent_locked to implement
    "sticky sessions" - keeping a user with the same agent until:
    - The agent completes its task (release_lock)
    - The user explicitly changes intent
    - The conversation expires
    
    Example state_data for trip_setup:
    {
        "trip_name": "Ecuador Adventure",
        "start_date": "2024-12-15",
        "end_date": "2024-12-30",
        "destination_country": "EC",
        "destination_city": "Quito"
    }
    """

    __tablename__ = "conversation_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Agent Routing (for Coordinator Agent)
    # ─────────────────────────────────────────────────────────────────────────
    active_agent: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "configuration", "ie", "coach", None
    
    agent_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # Is the session locked to this agent?
    
    lock_reason: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Why the session is locked (e.g., "expense_flow", "onboarding")
    
    lock_started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When the lock was acquired
    
    # Context passed between agents during handoffs
    handoff_context: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Data passed from one agent to another

    # ─────────────────────────────────────────────────────────────────────────
    # Conversation Context
    # ─────────────────────────────────────────────────────────────────────────
    current_flow: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # onboarding, trip_setup, card_setup, budget_config, expense, query
    current_step: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Step within the flow, e.g., "ask_name", "ask_currency"
    
    # State Data - accumulated data during conversation
    state_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Pending Actions
    # ─────────────────────────────────────────────────────────────────────────
    pending_confirmation: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # What we're waiting for user to confirm
    pending_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "trip", "budget", "card", "expense"
    pending_entity_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Data to be confirmed before persisting
    
    # ─────────────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────────────
    session_started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    
    # Status: active, completed, expired, cancelled
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Message History (for context)
    # ─────────────────────────────────────────────────────────────────────────
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_bot_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Full message history (optional, for complex flows)
    message_history: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=list
    )  # List of {"role": "user"|"bot", "content": "...", "timestamp": "..."}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Timestamps
    # ─────────────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="conversations")

    def __repr__(self) -> str:
        return (
            f"<ConversationState(id={self.id}, user_id={self.user_id}, "
            f"flow={self.current_flow}, step={self.current_step}, status={self.status})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if conversation is still active and not expired."""
        return self.status == "active" and datetime.utcnow() < self.expires_at

    @property
    def is_expired(self) -> bool:
        """Check if conversation has expired."""
        return datetime.utcnow() >= self.expires_at

    def touch(self, timeout_minutes: int = DEFAULT_CONVERSATION_TIMEOUT_MINUTES) -> None:
        """
        Update last interaction time and extend expiration.
        Call this on every user message.
        """
        now = datetime.utcnow()
        self.last_interaction_at = now
        self.expires_at = now + timedelta(minutes=timeout_minutes)
        self.updated_at = now

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the history.
        
        Args:
            role: "user" or "bot"
            content: Message content
        """
        if self.message_history is None:
            self.message_history = []
        
        self.message_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        self.message_count += 1
        
        if role == "user":
            self.last_user_message = content
        else:
            self.last_bot_message = content

    def update_state(self, **kwargs) -> None:
        """
        Update state_data with new values.
        
        Example:
            conversation.update_state(trip_name="Ecuador", start_date="2024-12-15")
        """
        if self.state_data is None:
            self.state_data = {}
        self.state_data.update(kwargs)

    def get_state(self, key: str, default=None):
        """Get a value from state_data."""
        if self.state_data is None:
            return default
        return self.state_data.get(key, default)

    def clear_pending(self) -> None:
        """Clear pending confirmation data."""
        self.pending_confirmation = None
        self.pending_entity_type = None
        self.pending_entity_data = None

    def set_pending(
        self, 
        confirmation: str, 
        entity_type: str, 
        entity_data: dict
    ) -> None:
        """
        Set pending confirmation data.
        
        Args:
            confirmation: Description of what needs confirmation
            entity_type: Type of entity (trip, budget, card, expense)
            entity_data: Data to persist after confirmation
        """
        self.pending_confirmation = confirmation
        self.pending_entity_type = entity_type
        self.pending_entity_data = entity_data

    def complete(self) -> None:
        """Mark conversation as completed."""
        self.status = "completed"
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        """Mark conversation as cancelled."""
        self.status = "cancelled"
        self.updated_at = datetime.utcnow()

    def expire(self) -> None:
        """Mark conversation as expired."""
        self.status = "expired"
        self.updated_at = datetime.utcnow()
        self.unlock_agent()  # Release lock on expiration

    # ─────────────────────────────────────────────────────────────────────────
    # Agent Routing Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def lock_to_agent(self, agent: str, reason: str | None = None) -> None:
        """
        Lock the conversation to a specific agent (sticky session).
        
        Args:
            agent: Agent name ("configuration", "ie", "coach")
            reason: Reason for the lock (e.g., "onboarding", "expense_flow")
        """
        self.active_agent = agent
        self.agent_locked = True
        self.lock_reason = reason
        self.lock_started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def unlock_agent(self) -> None:
        """Release the agent lock (allow re-routing)."""
        self.agent_locked = False
        self.lock_reason = None
        self.lock_started_at = None
        self.updated_at = datetime.utcnow()
        # Note: active_agent is preserved for context
    
    def set_active_agent(self, agent: str | None) -> None:
        """
        Set the active agent without locking.
        
        Args:
            agent: Agent name or None to clear
        """
        self.active_agent = agent
        self.updated_at = datetime.utcnow()
    
    def set_handoff_context(self, context: dict | None) -> None:
        """
        Set context data to be passed to the next agent.
        
        Args:
            context: Dictionary with context data, or None to clear
        """
        self.handoff_context = context
        self.updated_at = datetime.utcnow()
    
    def clear_handoff_context(self) -> None:
        """Clear the handoff context after it has been consumed."""
        self.handoff_context = None
        self.updated_at = datetime.utcnow()
    
    @property
    def is_agent_locked(self) -> bool:
        """Check if conversation is locked to an agent."""
        return self.agent_locked and self.active_agent is not None
    
    @property
    def has_handoff_context(self) -> bool:
        """Check if there is handoff context from a previous agent."""
        return self.handoff_context is not None and len(self.handoff_context) > 0

    @classmethod
    def create_new(
        cls,
        user_id: uuid.UUID,
        flow: str,
        step: str,
        timeout_minutes: int = DEFAULT_CONVERSATION_TIMEOUT_MINUTES,
        active_agent: str | None = None,
        agent_locked: bool = False,
        lock_reason: str | None = None,
    ) -> "ConversationState":
        """
        Factory method to create a new conversation state.
        
        Args:
            user_id: User UUID
            flow: Initial flow (onboarding, trip_setup, etc.)
            step: Initial step within the flow
            timeout_minutes: Session timeout in minutes
            active_agent: Agent to assign (optional)
            agent_locked: Whether to lock to the agent
            lock_reason: Reason for the lock
            
        Returns:
            New ConversationState instance
        """
        now = datetime.utcnow()
        return cls(
            user_id=user_id,
            current_flow=flow,
            current_step=step,
            state_data={},
            session_started_at=now,
            last_interaction_at=now,
            expires_at=now + timedelta(minutes=timeout_minutes),
            status="active",
            message_count=0,
            message_history=[],
            # Agent routing
            active_agent=active_agent,
            agent_locked=agent_locked,
            lock_reason=lock_reason,
            lock_started_at=now if agent_locked else None,
            handoff_context=None,
        )

