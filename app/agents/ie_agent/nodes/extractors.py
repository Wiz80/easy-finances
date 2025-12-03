"""
Extractor nodes for IE Agent.

Contains nodes for extracting expense data from different input types:
- Text: Direct text extraction
- Audio: Transcription + text extraction
- Image/Receipt: OCR + structured extraction
"""

from app.agents.ie_agent.state import IEAgentState
from app.logging_config import get_logger
from app.schemas.extraction import ExtractedExpense
from app.tools.extraction import (
    extract_expense_from_audio,
    extract_expense_from_text,
    extract_receipt_from_file,
)

logger = get_logger(__name__)


def extract_text_node(state: IEAgentState) -> IEAgentState:
    """
    Text extraction node: Extract expense from plain text.
    
    Args:
        state: Current agent state with raw_input as string
        
    Returns:
        Updated state with extracted_expense
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "extract_text_node_start",
        request_id=request_id,
        user_id=str(state.get("user_id")),
    )
    
    try:
        raw_input = state.get("raw_input")
        
        if not isinstance(raw_input, str):
            raise ValueError("Text extraction requires string input")
        
        # Extract expense using text extractor
        extracted = extract_expense_from_text(
            text=raw_input,
            request_id=request_id,
            user_id=str(state.get("user_id")),
        )
        
        logger.info(
            "extract_text_node_success",
            request_id=request_id,
            amount=float(extracted.amount),
            currency=extracted.currency,
            confidence=extracted.confidence,
        )
        
        return {
            **state,
            "extracted_expense": extracted,
            "confidence": extracted.confidence,
            "status": "extracting",
            "errors": state.get("errors", []),
        }
        
    except Exception as e:
        error_msg = f"Text extraction failed: {str(e)}"
        logger.error(
            "extract_text_node_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [error_msg],
            "error_node": "extract_text",
        }


def extract_audio_node(state: IEAgentState) -> IEAgentState:
    """
    Audio extraction node: Transcribe and extract expense from audio.
    
    Args:
        state: Current agent state with raw_input as bytes
        
    Returns:
        Updated state with transcription and extracted_expense
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "extract_audio_node_start",
        request_id=request_id,
        user_id=str(state.get("user_id")),
    )
    
    try:
        raw_input = state.get("raw_input")
        
        if not isinstance(raw_input, bytes):
            raise ValueError("Audio extraction requires bytes input")
        
        # Extract expense using audio extractor (includes transcription)
        extracted = extract_expense_from_audio(
            audio_file=raw_input,
            language=state.get("language"),
            request_id=request_id,
            user_id=str(state.get("user_id")),
        )
        
        # Get transcription from notes (added by audio_extractor)
        transcription = None
        if extracted.notes and extracted.notes.startswith("Transcription:"):
            transcription = extracted.notes.split("Transcription:", 1)[1].strip()
            # Also split out any additional notes
            if "\n" in transcription:
                transcription = transcription.split("\n")[0].strip()
        
        logger.info(
            "extract_audio_node_success",
            request_id=request_id,
            amount=float(extracted.amount),
            currency=extracted.currency,
            confidence=extracted.confidence,
            transcription_length=len(transcription) if transcription else 0,
        )
        
        return {
            **state,
            "extracted_expense": extracted,
            "transcription": transcription,
            "confidence": extracted.confidence,
            "status": "extracting",
            "errors": state.get("errors", []),
        }
        
    except Exception as e:
        error_msg = f"Audio extraction failed: {str(e)}"
        logger.error(
            "extract_audio_node_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [error_msg],
            "error_node": "extract_audio",
        }


def extract_image_node(state: IEAgentState) -> IEAgentState:
    """
    Image/Receipt extraction node: OCR and extract receipt data.
    
    This node handles both images and PDF receipts.
    It creates both an ExtractedReceipt AND converts it to ExtractedExpense.
    
    Args:
        state: Current agent state with raw_input as bytes
        
    Returns:
        Updated state with extracted_receipt and extracted_expense
    """
    request_id = state.get("request_id", "unknown")
    
    logger.info(
        "extract_image_node_start",
        request_id=request_id,
        user_id=str(state.get("user_id")),
        filename=state.get("filename"),
        file_type=state.get("file_type"),
    )
    
    try:
        raw_input = state.get("raw_input")
        
        if not isinstance(raw_input, bytes):
            raise ValueError("Image extraction requires bytes input")
        
        # Extract receipt using receipt parser
        extracted_receipt = extract_receipt_from_file(
            file_path=raw_input,
            filename=state.get("filename"),
            request_id=request_id,
            user_id=str(state.get("user_id")),
        )
        
        # Convert ExtractedReceipt to ExtractedExpense
        # This allows unified handling in validation and storage
        extracted_expense = _receipt_to_expense(extracted_receipt, state)
        
        logger.info(
            "extract_image_node_success",
            request_id=request_id,
            merchant=extracted_receipt.merchant,
            amount=float(extracted_receipt.total_amount),
            currency=extracted_receipt.currency,
            confidence=extracted_receipt.confidence,
            line_items_count=len(extracted_receipt.line_items),
        )
        
        return {
            **state,
            "extracted_receipt": extracted_receipt,
            "extracted_expense": extracted_expense,
            "confidence": extracted_receipt.confidence,
            "status": "extracting",
            "errors": state.get("errors", []),
        }
        
    except Exception as e:
        error_msg = f"Image extraction failed: {str(e)}"
        logger.error(
            "extract_image_node_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [error_msg],
            "error_node": "extract_image",
        }


def _receipt_to_expense(receipt, state: IEAgentState) -> ExtractedExpense:
    """
    Convert ExtractedReceipt to ExtractedExpense.
    
    This allows unified handling downstream (validation, storage).
    
    Args:
        receipt: ExtractedReceipt from image extraction
        state: Current agent state
        
    Returns:
        ExtractedExpense with data from receipt
    """
    from app.schemas.extraction import ExtractedReceipt
    
    # Determine payment method from receipt
    method = "cash"
    card_hint = None
    
    if receipt.payment_method:
        payment_lower = receipt.payment_method.lower()
        if any(card in payment_lower for card in ["visa", "mastercard", "amex", "card", "tarjeta", "débito", "crédito"]):
            method = "card"
            # Extract card hint
            for card_type in ["visa", "mastercard", "amex"]:
                if card_type in payment_lower:
                    card_hint = card_type.capitalize()
                    break
    
    # Build description from merchant and transaction type
    description = receipt.merchant
    if receipt.transaction_type:
        description = f"{receipt.transaction_type}: {receipt.merchant}"
    
    # Build raw_input from markdown or text
    raw_input = receipt.raw_markdown or receipt.raw_text or f"Receipt from {receipt.merchant}"
    if len(raw_input) > 2000:
        raw_input = raw_input[:2000]
    
    return ExtractedExpense(
        amount=receipt.total_amount,
        currency=receipt.currency,
        description=description,
        category_candidate=receipt.category_candidate,
        method=method,
        merchant=receipt.merchant,
        card_hint=card_hint,
        occurred_at=receipt.occurred_at,
        notes=f"Receipt number: {receipt.receipt_number}" if receipt.receipt_number else None,
        confidence=receipt.confidence,
        raw_input=raw_input,
    )


def error_node(state: IEAgentState) -> IEAgentState:
    """
    Error node: Handle routing errors (unknown input type).
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with error status
    """
    request_id = state.get("request_id", "unknown")
    input_type = state.get("input_type", "unknown")
    
    error_msg = f"Cannot process input type: {input_type}"
    
    logger.error(
        "error_node_invoked",
        request_id=request_id,
        input_type=input_type,
        error=error_msg,
    )
    
    return {
        **state,
        "status": "error",
        "errors": state.get("errors", []) + [error_msg],
        "error_node": "router",
    }

