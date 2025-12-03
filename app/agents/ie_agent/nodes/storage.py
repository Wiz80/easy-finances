"""
Storage node for IE Agent.

Persists extracted expense and receipt data to the database.
Uses the storage layer with idempotency checks.
"""

from app.agents.ie_agent.state import IEAgentState
from app.database import SessionLocal
from app.logging_config import get_logger
from app.storage import (
    create_expense,
    create_receipt,
)

logger = get_logger(__name__)


def store_expense_node(state: IEAgentState) -> IEAgentState:
    """
    Storage node: Persist expense and receipt to database.
    
    This node:
    1. Creates expense record with idempotency check
    2. If image/receipt input, also creates receipt record
    3. Handles duplicate detection
    
    Args:
        state: Current agent state with extracted data
        
    Returns:
        Updated state with expense_id and receipt_id
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "store_expense_node_start",
        request_id=request_id,
        user_id=str(state.get("user_id")),
        input_type=state.get("input_type"),
    )
    
    session = SessionLocal()
    
    try:
        extracted_expense = state.get("extracted_expense")
        
        if extracted_expense is None:
            raise ValueError("No extracted expense to store")
        
        # Map input_type to source_type
        input_type = state.get("input_type", "unknown")
        source_type_map = {
            "text": "text",
            "audio": "audio",
            "image": "image",
            "receipt": "receipt",
        }
        source_type = source_type_map.get(input_type, "unknown")
        
        # Create expense record
        expense_result = create_expense(
            session=session,
            extracted=extracted_expense,
            user_id=state["user_id"],
            account_id=state["account_id"],
            source_type=source_type,
            trip_id=state.get("trip_id"),
            card_id=state.get("card_id"),
            msg_id=state.get("msg_id"),
            content_hash=state.get("content_hash"),
            occurred_at_override=state.get("occurred_at_override"),
        )
        
        expense_id = expense_result.expense.id
        is_duplicate = not expense_result.created
        
        logger.info(
            "expense_stored",
            request_id=request_id,
            expense_id=str(expense_id),
            created=expense_result.created,
            duplicate_reason=expense_result.duplicate_reason,
        )
        
        # If this is an image/receipt input, also create receipt record
        receipt_id = None
        extracted_receipt = state.get("extracted_receipt")
        raw_input = state.get("raw_input")
        
        if (
            extracted_receipt is not None
            and isinstance(raw_input, bytes)
            and not is_duplicate  # Don't create receipt for duplicate expense
        ):
            receipt_result = create_receipt(
                session=session,
                expense_id=expense_id,
                file_bytes=raw_input,
                filename=state.get("filename") or "receipt.jpg",
                parsed_data=extracted_receipt,
                file_type=state.get("file_type") or "image/jpeg",
            )
            
            receipt_id = receipt_result.receipt.id
            
            # If receipt already existed, update duplicate status
            if not receipt_result.created:
                is_duplicate = True
            
            logger.info(
                "receipt_stored",
                request_id=request_id,
                receipt_id=str(receipt_id),
                expense_id=str(expense_id),
                created=receipt_result.created,
            )
        
        # Commit transaction
        session.commit()
        
        logger.info(
            "store_expense_node_complete",
            request_id=request_id,
            expense_id=str(expense_id),
            receipt_id=str(receipt_id) if receipt_id else None,
            is_duplicate=is_duplicate,
        )
        
        return {
            **state,
            "expense_id": expense_id,
            "receipt_id": receipt_id,
            "is_duplicate": is_duplicate,
            "status": "storing",
        }
        
    except Exception as e:
        session.rollback()
        error_msg = f"Storage failed: {str(e)}"
        
        logger.error(
            "store_expense_node_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [error_msg],
            "error_node": "store_expense",
        }
        
    finally:
        session.close()


def finalize_node(state: IEAgentState) -> IEAgentState:
    """
    Finalize node: Set final status based on execution results.
    
    This is the last node before END. It:
    1. Sets final status (completed, error, low_confidence)
    2. Logs final summary
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with final status
    """
    request_id = state.get("request_id", "unknown")
    current_status = state.get("status", "pending")
    
    # Determine final status
    if current_status == "error":
        final_status = "error"
    elif state.get("expense_id") is not None:
        # Successfully stored
        if state.get("confidence", 0) < 0.7:
            final_status = "low_confidence"
        else:
            final_status = "completed"
    else:
        # No expense created (validation failed, etc.)
        final_status = "error"
    
    logger.info(
        "finalize_node",
        request_id=request_id,
        final_status=final_status,
        expense_id=str(state.get("expense_id")) if state.get("expense_id") else None,
        receipt_id=str(state.get("receipt_id")) if state.get("receipt_id") else None,
        is_duplicate=state.get("is_duplicate", False),
        confidence=state.get("confidence"),
        error_count=len(state.get("errors", [])),
    )
    
    return {
        **state,
        "status": final_status,
    }

