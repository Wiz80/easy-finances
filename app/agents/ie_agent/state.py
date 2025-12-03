"""
IE Agent State Schema.

Defines the state that flows through the LangGraph nodes.
Based on LangGraph v1.x patterns: https://docs.langchain.com/oss/python/langgraph/overview
"""

from datetime import datetime
from typing import Any, Literal, TypedDict
from uuid import UUID

from app.schemas.extraction import ExtractedExpense, ExtractedReceipt


# Input types supported by the IE Agent
InputType = Literal["text", "audio", "image", "receipt", "unknown"]

# Status of the agent execution
AgentStatus = Literal[
    "pending",           # Initial state
    "routing",           # Determining input type
    "extracting",        # Running extraction
    "validating",        # Validating extracted data
    "storing",           # Persisting to database
    "completed",         # Successfully completed
    "error",             # Error occurred
    "low_confidence",    # Extraction confidence below threshold
]


class IEAgentState(TypedDict, total=False):
    """
    State schema for the Information Extraction Agent.
    
    This state flows through all nodes in the LangGraph and contains:
    - Input data (raw bytes, text, file info)
    - Context (user_id, account_id, trip_id)
    - Intermediate results (extracted data, transcriptions)
    - Output (expense_id, receipt_id, status)
    - Error tracking
    
    Usage:
        state = IEAgentState(
            input_type="text",
            raw_input="Gasté 50 soles en taxi",
            user_id=user.id,
            account_id=account.id,
        )
    """
    
    # =========================================================================
    # Request Identity (for logging and tracing)
    # =========================================================================
    request_id: str  # Unique ID for this request (for tracing)
    
    # =========================================================================
    # Input Data
    # =========================================================================
    input_type: InputType  # Detected or specified input type
    raw_input: str | bytes | None  # Raw input (text string or file bytes)
    filename: str | None  # Original filename (for receipts/images)
    file_type: str | None  # MIME type (e.g., image/jpeg, application/pdf)
    msg_id: str | None  # WhatsApp/source message ID for idempotency
    
    # =========================================================================
    # Context (Required for Storage)
    # =========================================================================
    user_id: UUID  # User who submitted the expense
    account_id: UUID  # Account to charge
    trip_id: UUID | None  # Optional trip context
    card_id: UUID | None  # Optional card used
    
    # =========================================================================
    # Extraction Options
    # =========================================================================
    language: str | None  # Preferred language for transcription
    occurred_at_override: datetime | None  # Override expense date
    
    # =========================================================================
    # Intermediate Results
    # =========================================================================
    transcription: str | None  # Audio transcription (if audio input)
    extracted_expense: ExtractedExpense | None  # Extracted expense data
    extracted_receipt: ExtractedReceipt | None  # Extracted receipt data (if image)
    content_hash: str | None  # SHA256 hash of input content
    
    # =========================================================================
    # Validation Results
    # =========================================================================
    confidence: float  # Final confidence score
    validation_passed: bool  # Whether validation succeeded
    validation_errors: list[str]  # List of validation issues
    
    # =========================================================================
    # Output (Final Results)
    # =========================================================================
    expense_id: UUID | None  # Created expense ID
    receipt_id: UUID | None  # Created receipt ID (if applicable)
    status: AgentStatus  # Current status
    is_duplicate: bool  # Whether this was a duplicate
    
    # =========================================================================
    # Error Tracking
    # =========================================================================
    errors: list[str]  # List of error messages
    error_node: str | None  # Node where error occurred


def create_initial_state(
    user_id: UUID,
    account_id: UUID,
    raw_input: str | bytes,
    input_type: InputType = "unknown",
    request_id: str | None = None,
    **kwargs: Any,
) -> IEAgentState:
    """
    Create initial state for IE Agent execution.
    
    Args:
        user_id: User ID
        account_id: Account ID
        raw_input: Raw input (text or bytes)
        input_type: Type of input (auto-detect if unknown)
        request_id: Optional request ID (generated if not provided)
        **kwargs: Additional state fields
        
    Returns:
        IEAgentState ready for graph execution
        
    Example:
        >>> state = create_initial_state(
        ...     user_id=user.id,
        ...     account_id=account.id,
        ...     raw_input="50 soles taxi",
        ...     input_type="text",
        ... )
    """
    import uuid
    
    return IEAgentState(
        request_id=request_id or str(uuid.uuid4()),
        input_type=input_type,
        raw_input=raw_input,
        filename=kwargs.get("filename"),
        file_type=kwargs.get("file_type"),
        msg_id=kwargs.get("msg_id"),
        user_id=user_id,
        account_id=account_id,
        trip_id=kwargs.get("trip_id"),
        card_id=kwargs.get("card_id"),
        language=kwargs.get("language"),
        occurred_at_override=kwargs.get("occurred_at_override"),
        transcription=None,
        extracted_expense=None,
        extracted_receipt=None,
        content_hash=None,
        confidence=0.0,
        validation_passed=False,
        validation_errors=[],
        expense_id=None,
        receipt_id=None,
        status="pending",
        is_duplicate=False,
        errors=[],
        error_node=None,
    )

