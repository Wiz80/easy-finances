"""
Validator node for IE Agent.

Validates extracted expense data and checks confidence thresholds.
"""

from typing import Literal

from app.agents.ie_agent.state import IEAgentState
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def validate_extraction_node(state: IEAgentState) -> IEAgentState:
    """
    Validation node: Validate extracted expense data.
    
    Checks:
    1. Required fields are present (amount, currency, description)
    2. Amount is positive and reasonable
    3. Currency is valid ISO 4217 code
    4. Confidence meets threshold
    
    Args:
        state: Current agent state with extracted_expense
        
    Returns:
        Updated state with validation results
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "validate_extraction_node_start",
        request_id=request_id,
    )
    
    validation_errors = []
    extracted = state.get("extracted_expense")
    
    # Check if extraction produced results
    if extracted is None:
        validation_errors.append("No expense data extracted")
        return {
            **state,
            "validation_passed": False,
            "validation_errors": validation_errors,
            "status": "error",
        }
    
    # Validate required fields
    if not extracted.amount or extracted.amount <= 0:
        validation_errors.append(f"Invalid amount: {extracted.amount}")
    
    if not extracted.currency or len(extracted.currency) != 3:
        validation_errors.append(f"Invalid currency code: {extracted.currency}")
    
    if not extracted.description or len(extracted.description.strip()) == 0:
        validation_errors.append("Missing description")
    
    # Validate amount is reasonable (not absurdly high)
    MAX_AMOUNT = 10000000  # Maximum single expense
    if extracted.amount and extracted.amount > MAX_AMOUNT:
        validation_errors.append(f"Amount exceeds maximum: {extracted.amount}")
    
    # Validate currency is known
    KNOWN_CURRENCIES = {
        "USD", "EUR", "GBP", "JPY", "CNY", "INR", "BRL", "MXN",
        "PEN", "COP", "ARS", "CLP", "BOB", "VES", "UYU", "PYG",
        "CAD", "AUD", "NZD", "CHF", "SEK", "NOK", "DKK", "PLN",
        "CZK", "HUF", "RON", "BGN", "HRK", "RUB", "TRY", "ZAR",
        "KRW", "SGD", "HKD", "TWD", "THB", "MYR", "IDR", "PHP",
        "VND", "PKR", "BDT", "EGP", "NGN", "KES", "GHS", "MAD",
        "AED", "SAR", "ILS", "QAR", "KWD", "BHD", "OMR",
    }
    if extracted.currency and extracted.currency.upper() not in KNOWN_CURRENCIES:
        validation_errors.append(f"Unknown currency: {extracted.currency}")
    
    # Check confidence threshold
    confidence = state.get("confidence", 0.0)
    confidence_threshold = settings.confidence_threshold
    
    is_low_confidence = confidence < confidence_threshold
    if is_low_confidence:
        validation_errors.append(
            f"Confidence {confidence:.2f} below threshold {confidence_threshold}"
        )
    
    # Determine validation result
    # Critical errors (missing data) = fail
    # Low confidence = flag but can continue
    critical_errors = [e for e in validation_errors if "Invalid" in e or "Missing" in e or "exceeds" in e]
    
    validation_passed = len(critical_errors) == 0
    
    # Determine status
    if not validation_passed:
        status = "error"
    elif is_low_confidence:
        status = "low_confidence"
    else:
        status = "validating"
    
    logger.info(
        "validate_extraction_node_complete",
        request_id=request_id,
        validation_passed=validation_passed,
        is_low_confidence=is_low_confidence,
        confidence=confidence,
        error_count=len(validation_errors),
        status=status,
    )
    
    return {
        **state,
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
        "status": status,
    }


def get_storage_route(state: IEAgentState) -> Literal["store_expense", "end"]:
    """
    Conditional edge function: Determine whether to store or skip.
    
    Stores if:
    - Validation passed (no critical errors)
    - Even with low confidence (will be pending_confirm)
    
    Skips if:
    - Validation failed (critical errors)
    - Already in error state
    
    Args:
        state: Current agent state
        
    Returns:
        "store_expense" or "end"
    """
    status = state.get("status", "pending")
    validation_passed = state.get("validation_passed", False)
    
    # Error state = skip storage
    if status == "error":
        logger.debug(
            "storage_route_skip",
            request_id=state.get("request_id"),
            reason="error_status",
        )
        return "end"
    
    # Validation failed = skip storage
    if not validation_passed:
        logger.debug(
            "storage_route_skip",
            request_id=state.get("request_id"),
            reason="validation_failed",
        )
        return "end"
    
    # Otherwise, proceed to storage
    logger.debug(
        "storage_route_store",
        request_id=state.get("request_id"),
        status=status,
    )
    return "store_expense"

