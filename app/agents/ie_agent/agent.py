"""
IE Agent - Main Entry Point.

The Information Extraction Agent processes multi-modal inputs (text, audio, images)
and extracts structured expense data, storing it in the database.

Usage:
    from app.agents.ie_agent import process_expense
    
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input="Gasté 50 soles en taxi",
        input_type="text",
    )
    
    if result["status"] == "completed":
        print(f"Created expense: {result['expense_id']}")
"""

from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID

from app.agents.ie_agent.graph import get_ie_agent_graph
from app.agents.ie_agent.state import (
    AgentStatus,
    IEAgentState,
    InputType,
    create_initial_state,
)
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.agents.common.response import AgentResponse

logger = get_logger(__name__)


class IEAgentResult:
    """
    Result object from IE Agent execution.
    
    Provides convenient access to execution results with type hints.
    """
    
    def __init__(self, state: IEAgentState):
        self._state = state
    
    @property
    def success(self) -> bool:
        """Whether the agent completed successfully."""
        return self._state.get("status") in ("completed", "low_confidence")
    
    @property
    def status(self) -> AgentStatus:
        """Final status of the agent execution."""
        return self._state.get("status", "error")
    
    @property
    def expense_id(self) -> UUID | None:
        """Created expense ID (if successful)."""
        return self._state.get("expense_id")
    
    @property
    def receipt_id(self) -> UUID | None:
        """Created receipt ID (if applicable)."""
        return self._state.get("receipt_id")
    
    @property
    def is_duplicate(self) -> bool:
        """Whether this was detected as a duplicate."""
        return self._state.get("is_duplicate", False)
    
    @property
    def confidence(self) -> float:
        """Extraction confidence score."""
        return self._state.get("confidence", 0.0)
    
    @property
    def errors(self) -> list[str]:
        """List of error messages."""
        return self._state.get("errors", [])
    
    @property
    def validation_errors(self) -> list[str]:
        """List of validation issues."""
        return self._state.get("validation_errors", [])
    
    @property
    def extracted_expense(self):
        """The extracted expense data."""
        return self._state.get("extracted_expense")
    
    @property
    def extracted_receipt(self):
        """The extracted receipt data (if image input)."""
        return self._state.get("extracted_receipt")
    
    @property
    def state(self) -> IEAgentState:
        """Full state dict."""
        return self._state
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "status": self.status,
            "expense_id": str(self.expense_id) if self.expense_id else None,
            "receipt_id": str(self.receipt_id) if self.receipt_id else None,
            "is_duplicate": self.is_duplicate,
            "confidence": self.confidence,
            "errors": self.errors,
            "validation_errors": self.validation_errors,
        }
    
    def to_agent_response(self, request_id: str | None = None) -> "AgentResponse":
        """
        Convert to unified AgentResponse format.
        
        This enables seamless integration with the Coordinator Agent.
        
        Args:
            request_id: Optional request ID for tracing
            
        Returns:
            AgentResponse with expense extraction result
        """
        from app.agents.common.response import AgentResponse, AgentStatus as UnifiedStatus
        
        # Map status
        status_map = {
            "completed": UnifiedStatus.COMPLETED,
            "low_confidence": UnifiedStatus.COMPLETED,
            "error": UnifiedStatus.ERROR,
            "pending": UnifiedStatus.AWAITING_INPUT,
        }
        unified_status = status_map.get(self.status, UnifiedStatus.COMPLETED)
        
        # Build response text
        response_text = self._build_response_text()
        
        # IE Agent usually completes in one turn (no pending field)
        # Always release lock and hand back to coordinator
        return AgentResponse(
            response_text=response_text,
            status=unified_status,
            agent_name="ie",
            request_id=request_id or self._state.get("request_id"),
            confidence=self.confidence,
            # Created entity
            created_expense_id=self.expense_id,
            # Lock management - IE agent completes in one turn
            release_lock=True,
            continue_flow=False,
            # Handoff back to coordinator
            handoff_to="coordinator",
            handoff_reason="expense_completed",
            # Errors
            errors=self.errors + self.validation_errors,
        )
    
    def _build_response_text(self) -> str:
        """Build user-friendly response text."""
        if self.is_duplicate:
            return "ℹ️ Este gasto ya fue registrado anteriormente."
        
        if self.status == "error":
            error_msg = self.errors[0] if self.errors else "Error desconocido"
            return f"⚠️ No pude registrar el gasto: {error_msg}"
        
        if self.status == "low_confidence":
            expense = self.extracted_expense
            if expense:
                return (
                    f"🤔 Registré el gasto pero con poca confianza:\n"
                    f"• Monto: {expense.amount} {expense.currency}\n"
                    f"• Descripción: {expense.description or 'Sin descripción'}\n"
                    f"¿Es correcto? Si no, puedes corregirlo."
                )
            return "🤔 No estoy seguro de haber entendido bien. ¿Puedes darme más detalles?"
        
        # Success
        expense = self.extracted_expense
        if expense:
            amount_str = f"{expense.amount:,.2f}" if expense.amount else "?"
            currency = expense.currency or "?"
            description = expense.description or "Gasto"
            category = getattr(expense, "category_candidate", "") or ""
            
            # Category emoji
            emoji_map = {
                "FOOD": "🍔",
                "LODGING": "🏨",
                "TRANSPORT": "🚕",
                "TOURISM": "🎭",
                "SHOPPING": "🛍️",
                "MISC": "📦",
            }
            category_emoji = emoji_map.get(category.upper(), "💰")
            
            return (
                f"✅ {category_emoji} Gasto registrado:\n"
                f"• {description}: {amount_str} {currency}"
            )
        
        return "✅ Gasto registrado correctamente."
    
    def __repr__(self) -> str:
        return (
            f"IEAgentResult(success={self.success}, status={self.status}, "
            f"expense_id={self.expense_id}, confidence={self.confidence:.2f})"
        )


def process_expense(
    user_id: UUID,
    account_id: UUID,
    raw_input: str | bytes,
    input_type: InputType = "unknown",
    trip_id: UUID | None = None,
    card_id: UUID | None = None,
    msg_id: str | None = None,
    filename: str | None = None,
    file_type: str | None = None,
    language: str | None = None,
    occurred_at_override: datetime | None = None,
    request_id: str | None = None,
) -> IEAgentResult:
    """
    Process an expense input through the IE Agent.
    
    This is the main entry point for the IE Agent. It:
    1. Creates initial state from parameters
    2. Runs the LangGraph agent
    3. Returns structured result
    
    Args:
        user_id: User ID who owns this expense
        account_id: Account ID to charge
        raw_input: Input data (text string or file bytes)
        input_type: Type hint for input (auto-detect if "unknown")
        trip_id: Optional trip ID for context
        card_id: Optional card ID if known
        msg_id: Optional message ID for idempotency
        filename: Original filename (for images/PDFs)
        file_type: MIME type (for images/PDFs)
        language: Preferred language for transcription
        occurred_at_override: Override expense date
        request_id: Request ID for tracing
        
    Returns:
        IEAgentResult with execution results
        
    Example:
        >>> result = process_expense(
        ...     user_id=user.id,
        ...     account_id=account.id,
        ...     raw_input="Pagué 25 soles por el almuerzo",
        ...     input_type="text",
        ... )
        >>> print(f"Status: {result.status}, Expense: {result.expense_id}")
    """
    import uuid
    
    # Generate request ID if not provided
    request_id = request_id or str(uuid.uuid4())
    
    logger.info(
        "ie_agent_process_start",
        request_id=request_id,
        user_id=str(user_id),
        input_type=input_type,
        has_msg_id=msg_id is not None,
        has_filename=filename is not None,
    )
    
    try:
        # Create initial state
        initial_state = create_initial_state(
            user_id=user_id,
            account_id=account_id,
            raw_input=raw_input,
            input_type=input_type,
            request_id=request_id,
            trip_id=trip_id,
            card_id=card_id,
            msg_id=msg_id,
            filename=filename,
            file_type=file_type,
            language=language,
            occurred_at_override=occurred_at_override,
        )
        
        # Get compiled graph
        graph = get_ie_agent_graph()
        
        # Execute graph
        logger.debug("ie_agent_graph_invoke_start", request_id=request_id)
        final_state = graph.invoke(initial_state)
        logger.debug("ie_agent_graph_invoke_complete", request_id=request_id)
        
        # Create result object
        result = IEAgentResult(final_state)
        
        logger.info(
            "ie_agent_process_complete",
            request_id=request_id,
            success=result.success,
            status=result.status,
            expense_id=str(result.expense_id) if result.expense_id else None,
            is_duplicate=result.is_duplicate,
            confidence=result.confidence,
            error_count=len(result.errors),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "ie_agent_process_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        # Return error result
        error_state = IEAgentState(
            request_id=request_id,
            user_id=user_id,
            account_id=account_id,
            status="error",
            errors=[f"Agent execution failed: {str(e)}"],
            error_node="agent",
        )
        
        return IEAgentResult(error_state)


# Convenience aliases
process = process_expense
run = process_expense

