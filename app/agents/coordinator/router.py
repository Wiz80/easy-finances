"""
Intent Router for the Coordinator Agent.

This module provides intent detection to determine which agent should
handle a user message. It uses a hybrid approach:

1. Fast path: Keyword matching for obvious cases (no LLM call)
2. Slow path: LLM classification for ambiguous cases

The router also handles:
- Special coordinator commands (cancel, help, menu)
- Intent change detection within active sessions
- Context-aware routing based on user state
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.common.intents import (
    AgentType,
    EXPENSE_KEYWORDS,
    QUERY_KEYWORDS,
    CONFIG_KEYWORDS,
    COORDINATOR_COMMANDS,
    INTERCEPT_COMMANDS,
    detect_intent_fast,
    is_coordinator_command,
)
from app.config import settings
from app.logging_config import get_logger
from app.prompts.coordinator import (
    AGENT_ROUTING_SYSTEM,
    AGENT_ROUTING_USER,
    build_routing_prompt,
    build_intent_change_prompt,
)

logger = get_logger(__name__)


@dataclass
class RoutingResult:
    """Result of intent routing."""
    
    agent: AgentType
    confidence: float
    method: str  # "keyword", "llm", "forced", "command"
    command_action: str | None = None  # If it's a coordinator command
    reason: str | None = None
    
    @property
    def is_command(self) -> bool:
        """Check if this is a coordinator command."""
        return self.method == "command" and self.command_action is not None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent": self.agent.value,
            "confidence": self.confidence,
            "method": self.method,
            "command_action": self.command_action,
            "reason": self.reason,
        }


@dataclass
class IntentChangeResult:
    """Result of intent change detection."""
    
    should_change: bool
    new_agent: AgentType | None
    reason: str | None
    confidence: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "should_change": self.should_change,
            "new_agent": self.new_agent.value if self.new_agent else None,
            "reason": self.reason,
            "confidence": self.confidence,
        }


class IntentRouter:
    """
    Router that determines which agent should handle a message.
    
    Uses hybrid approach:
    1. Check for special commands (cancel, help, etc.)
    2. Try keyword-based fast detection
    3. Fall back to LLM for ambiguous cases
    
    Example:
        >>> router = IntentRouter()
        >>> result = await router.route("Gasté 50 soles en taxi", user_context)
        >>> print(result.agent)  # AgentType.IE
        >>> print(result.method)  # "keyword"
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ):
        """
        Initialize the router.
        
        Args:
            model_name: LLM model for ambiguous cases
            temperature: Temperature for LLM (0 for deterministic)
        """
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
    
    @property
    def llm(self) -> ChatOpenAI:
        """Lazy initialization of LLM."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=settings.openai_api_key,
            )
        return self._llm
    
    async def route(
        self,
        message: str,
        onboarding_completed: bool = True,
        has_active_trip: bool = False,
        last_agent: str | None = None,
        force_agent: AgentType | None = None,
    ) -> RoutingResult:
        """
        Determine which agent should handle the message.
        
        Args:
            message: User's message text
            onboarding_completed: Whether user finished onboarding
            has_active_trip: Whether user has an active trip
            last_agent: Last agent used (for context)
            force_agent: Force routing to specific agent (bypass detection)
            
        Returns:
            RoutingResult with agent and metadata
        """
        # 0. Force agent if specified
        if force_agent is not None:
            logger.debug(
                "route_forced",
                agent=force_agent.value,
                message_preview=message[:50],
            )
            return RoutingResult(
                agent=force_agent,
                confidence=1.0,
                method="forced",
                reason="Agent forced by caller",
            )
        
        # 1. Check for coordinator commands
        is_cmd, cmd_action = is_coordinator_command(message)
        if is_cmd:
            logger.debug(
                "route_command",
                command=cmd_action,
                message=message,
            )
            return RoutingResult(
                agent=AgentType.COORDINATOR,
                confidence=1.0,
                method="command",
                command_action=cmd_action,
                reason=f"Coordinator command: {cmd_action}",
            )
        
        # 2. Check if onboarding is required
        if not onboarding_completed:
            logger.debug(
                "route_onboarding_required",
                message_preview=message[:50],
            )
            return RoutingResult(
                agent=AgentType.CONFIGURATION,
                confidence=1.0,
                method="forced",
                reason="Onboarding not completed",
            )
        
        # 3. Try fast keyword-based detection
        fast_result = detect_intent_fast(message)
        if fast_result is not None and fast_result != AgentType.UNKNOWN:
            logger.debug(
                "route_keyword",
                agent=fast_result.value,
                message_preview=message[:50],
            )
            return RoutingResult(
                agent=fast_result,
                confidence=0.85,
                method="keyword",
                reason="Detected via keyword matching",
            )
        
        # 4. Fall back to LLM for ambiguous cases
        return await self._route_with_llm(
            message=message,
            onboarding_completed=onboarding_completed,
            has_active_trip=has_active_trip,
            last_agent=last_agent,
        )
    
    async def _route_with_llm(
        self,
        message: str,
        onboarding_completed: bool,
        has_active_trip: bool,
        last_agent: str | None,
    ) -> RoutingResult:
        """
        Use LLM to determine intent when keywords are ambiguous.
        
        Args:
            message: User's message
            onboarding_completed: Onboarding status
            has_active_trip: Trip status
            last_agent: Previous agent
            
        Returns:
            RoutingResult from LLM classification
        """
        try:
            system_prompt, user_prompt = build_routing_prompt(
                message=message,
                onboarding_completed=onboarding_completed,
                has_active_trip=has_active_trip,
                last_agent=last_agent,
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            response = await self.llm.ainvoke(messages)
            result_text = response.content.strip().lower()
            
            # Parse LLM response
            agent = self._parse_agent_response(result_text)
            
            logger.debug(
                "route_llm",
                agent=agent.value,
                llm_response=result_text,
                message_preview=message[:50],
            )
            
            return RoutingResult(
                agent=agent,
                confidence=0.75,  # LLM has lower confidence than keywords
                method="llm",
                reason=f"LLM classification: {result_text}",
            )
            
        except Exception as e:
            logger.error(
                "route_llm_error",
                error=str(e),
                message_preview=message[:50],
            )
            # Default to coach on error (safest fallback)
            return RoutingResult(
                agent=AgentType.COACH,
                confidence=0.5,
                method="llm",
                reason=f"LLM error, defaulting to coach: {str(e)}",
            )
    
    def _parse_agent_response(self, response: str) -> AgentType:
        """
        Parse LLM response into AgentType.
        
        Args:
            response: LLM response text
            
        Returns:
            Parsed AgentType
        """
        response_clean = response.strip().lower()
        
        # Direct match
        if "configuration" in response_clean:
            return AgentType.CONFIGURATION
        if "expense" in response_clean:
            return AgentType.IE
        if "query" in response_clean:
            return AgentType.COACH
        
        # Fallback to coach for questions
        return AgentType.COACH
    
    async def detect_intent_change(
        self,
        message: str,
        current_agent: str,
        last_bot_message: str | None = None,
    ) -> IntentChangeResult:
        """
        Detect if user wants to change agents mid-conversation.
        
        This is called when a session is locked to an agent, to determine
        if the user's message indicates they want to do something different.
        
        Args:
            message: User's current message
            current_agent: Currently active agent
            last_bot_message: Last message from the bot
            
        Returns:
            IntentChangeResult indicating if change is needed
        """
        # First check for explicit commands
        is_cmd, cmd_action = is_coordinator_command(message)
        if is_cmd:
            return IntentChangeResult(
                should_change=True,
                new_agent=AgentType.COORDINATOR,
                reason=f"User issued command: {cmd_action}",
                confidence=1.0,
            )
        
        # Quick keyword check for obvious changes
        quick_change = self._quick_intent_change_check(message, current_agent)
        if quick_change is not None:
            return quick_change
        
        # Use LLM for subtle changes
        return await self._detect_intent_change_llm(
            message=message,
            current_agent=current_agent,
            last_bot_message=last_bot_message,
        )
    
    def _quick_intent_change_check(
        self,
        message: str,
        current_agent: str,
    ) -> IntentChangeResult | None:
        """
        Quick keyword-based check for obvious intent changes.
        
        Returns None if change is ambiguous and needs LLM.
        """
        message_lower = message.lower()
        
        # Currently in expense flow
        if current_agent == "ie":
            # Check if user is asking a question
            if any(kw in message_lower for kw in ["cuánto", "cuanto", "qué", "que", "cómo", "como"]):
                # But not if it's clarifying the expense
                if not any(kw in message_lower for kw in ["gastó", "gasto", "pagué", "pagué"]):
                    return IntentChangeResult(
                        should_change=True,
                        new_agent=AgentType.COACH,
                        reason="Question detected while in expense flow",
                        confidence=0.8,
                    )
        
        # Currently in query flow
        if current_agent == "coach":
            # Check if user is logging an expense
            expense_indicators = ["gasté", "gaste", "pagué", "pague", "compré", "compre"]
            if any(kw in message_lower for kw in expense_indicators):
                # Check for number
                if re.search(r'\d+', message):
                    return IntentChangeResult(
                        should_change=True,
                        new_agent=AgentType.IE,
                        reason="Expense detected while in query flow",
                        confidence=0.85,
                    )
        
        # Currently in configuration flow
        if current_agent == "configuration":
            # Check for clear expense
            expense_indicators = ["gasté", "gaste", "pagué", "pague"]
            if any(kw in message_lower for kw in expense_indicators) and re.search(r'\d+', message):
                return IntentChangeResult(
                    should_change=True,
                    new_agent=AgentType.IE,
                    reason="Expense detected while in config flow",
                    confidence=0.85,
                )
        
        return None  # Needs LLM
    
    async def _detect_intent_change_llm(
        self,
        message: str,
        current_agent: str,
        last_bot_message: str | None,
    ) -> IntentChangeResult:
        """
        Use LLM to detect subtle intent changes.
        """
        try:
            system_prompt, user_prompt = build_intent_change_prompt(
                message=message,
                current_agent=current_agent,
                last_bot_message=last_bot_message,
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            response = await self.llm.ainvoke(messages)
            result_text = response.content.strip()
            
            # Parse JSON response
            result = self._parse_intent_change_response(result_text)
            
            logger.debug(
                "intent_change_llm",
                should_change=result.should_change,
                new_agent=result.new_agent.value if result.new_agent else None,
                reason=result.reason,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "intent_change_llm_error",
                error=str(e),
            )
            # Default to no change on error
            return IntentChangeResult(
                should_change=False,
                new_agent=None,
                reason=f"Error detecting change: {str(e)}",
                confidence=0.5,
            )
    
    def _parse_intent_change_response(self, response: str) -> IntentChangeResult:
        """
        Parse LLM response for intent change detection.
        """
        try:
            # Try to parse as JSON
            data = json.loads(response)
            
            should_change = data.get("should_change", False)
            new_agent_str = data.get("new_agent")
            reason = data.get("reason", "")
            
            new_agent = None
            if should_change and new_agent_str:
                new_agent_str = new_agent_str.lower()
                if "config" in new_agent_str:
                    new_agent = AgentType.CONFIGURATION
                elif "expense" in new_agent_str:
                    new_agent = AgentType.IE
                elif "query" in new_agent_str:
                    new_agent = AgentType.COACH
            
            return IntentChangeResult(
                should_change=should_change,
                new_agent=new_agent,
                reason=reason,
                confidence=0.75,
            )
            
        except json.JSONDecodeError:
            # Try to parse as simple text
            response_lower = response.lower()
            should_change = "true" in response_lower or "should_change" in response_lower
            
            return IntentChangeResult(
                should_change=should_change,
                new_agent=None,
                reason="Parsed from non-JSON response",
                confidence=0.5,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience functions
# ─────────────────────────────────────────────────────────────────────────────

# Singleton router instance
_router: IntentRouter | None = None


def get_router() -> IntentRouter:
    """Get the singleton router instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router


async def detect_agent_for_message(
    message: str,
    onboarding_completed: bool = True,
    has_active_trip: bool = False,
    last_agent: str | None = None,
    force_agent: AgentType | None = None,
) -> RoutingResult:
    """
    Convenience function to detect agent for a message.
    
    Args:
        message: User's message text
        onboarding_completed: Whether onboarding is done
        has_active_trip: Whether there's an active trip
        last_agent: Last agent used
        force_agent: Force a specific agent
        
    Returns:
        RoutingResult
    """
    router = get_router()
    return await router.route(
        message=message,
        onboarding_completed=onboarding_completed,
        has_active_trip=has_active_trip,
        last_agent=last_agent,
        force_agent=force_agent,
    )


async def detect_intent_change(
    message: str,
    current_agent: str,
    last_bot_message: str | None = None,
) -> IntentChangeResult:
    """
    Convenience function to detect intent changes.
    
    Args:
        message: User's message
        current_agent: Currently active agent
        last_bot_message: Last bot message
        
    Returns:
        IntentChangeResult
    """
    router = get_router()
    return await router.detect_intent_change(
        message=message,
        current_agent=current_agent,
        last_bot_message=last_bot_message,
    )


def reset_router() -> None:
    """Reset the singleton router (useful for testing)."""
    global _router
    _router = None

