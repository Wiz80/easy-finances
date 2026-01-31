"""
Receipt writer module for persisting parsed receipt data.
Handles idempotency via content hash (SHA256) and links to expenses.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.receipt import Receipt
from app.schemas.extraction import ExtractedReceipt
from app.storage.object_storage import compute_file_hash, upload_file

logger = get_logger(__name__)


@dataclass
class ReceiptWriteResult:
    """Result of a receipt write operation."""
    
    receipt: Receipt
    created: bool  # True if newly created, False if duplicate found
    duplicate_reason: str | None = None  # If duplicate, why


def _find_duplicate_receipt(
    session: Session,
    content_hash: str,
) -> Receipt | None:
    """
    Check for duplicate receipt by content hash.
    
    Args:
        session: Database session
        content_hash: SHA256 hash of the file content
        
    Returns:
        Existing Receipt if duplicate found, None otherwise
    """
    existing = session.query(Receipt).filter(
        Receipt.content_hash == content_hash
    ).first()
    
    if existing:
        logger.info(
            "duplicate_receipt_found",
            reason="content_hash",
            hash=content_hash[:16],
            receipt_id=str(existing.id),
            expense_id=str(existing.expense_id),
        )
    
    return existing


def _build_parsed_data(extracted: ExtractedReceipt) -> dict:
    """
    Build parsed_data JSONB from extracted receipt.
    
    Args:
        extracted: ExtractedReceipt data
        
    Returns:
        dict with structured receipt data for JSONB storage
    """
    # Convert line items to dicts
    line_items = [
        {
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price) if item.unit_price else None,
            "amount": float(item.amount),
        }
        for item in extracted.line_items
    ]
    
    return {
        "merchant": extracted.merchant,
        "total_amount": float(extracted.total_amount),
        "currency": extracted.currency,
        "occurred_at": extracted.occurred_at.isoformat() if extracted.occurred_at else None,
        "line_items": line_items,
        "tax_amount": float(extracted.tax_amount) if extracted.tax_amount else None,
        "tip_amount": float(extracted.tip_amount) if extracted.tip_amount else None,
        "payment_method": extracted.payment_method,
        "receipt_number": extracted.receipt_number,
        "category_candidate": extracted.category_candidate,
        "confidence": extracted.confidence,
        # Transaction specific fields
        "recipient": extracted.recipient,
        "sender": extracted.sender,
        "transaction_type": extracted.transaction_type,
        "bank_name": extracted.bank_name,
        "account_number": extracted.account_number,
        "reference_code": extracted.reference_code,
    }


def create_receipt(
    session: Session,
    expense_id: UUID,
    file_bytes: bytes,
    filename: str,
    parsed_data: ExtractedReceipt,
    file_type: str,
    ocr_provider: str = "llamaparse",
) -> ReceiptWriteResult:
    """
    Create a receipt record from parsed receipt data with idempotency.
    
    This function handles:
    - Duplicate detection via content hash (SHA256)
    - Upload to object storage
    - Link to expense via expense_id
    
    Args:
        session: Database session
        expense_id: Expense ID to link this receipt to
        file_bytes: Raw file bytes (image or PDF)
        filename: Original filename (for extension)
        parsed_data: ExtractedReceipt from parsing tools
        file_type: MIME type (e.g., image/jpeg, application/pdf)
        ocr_provider: OCR provider used (default: llamaparse)
        
    Returns:
        ReceiptWriteResult with receipt and creation status
        
    Example:
        >>> result = create_receipt(
        ...     session=db,
        ...     expense_id=expense.id,
        ...     file_bytes=image_bytes,
        ...     filename="receipt.jpg",
        ...     parsed_data=extracted_receipt,
        ...     file_type="image/jpeg",
        ... )
        >>> if result.created:
        ...     print(f"New receipt: {result.receipt.id}")
        ... else:
        ...     print(f"Duplicate: {result.receipt.id}")
    """
    # Compute content hash for deduplication
    content_hash = compute_file_hash(file_bytes)
    
    logger.debug(
        "creating_receipt",
        expense_id=str(expense_id),
        filename=filename,
        file_type=file_type,
        hash=content_hash[:16],
        size_bytes=len(file_bytes),
    )
    
    # Check for duplicates
    existing = _find_duplicate_receipt(session, content_hash)
    
    if existing:
        logger.info(
            "receipt_duplicate_returned",
            receipt_id=str(existing.id),
            expense_id=str(existing.expense_id),
            hash=content_hash[:16],
        )
        return ReceiptWriteResult(
            receipt=existing,
            created=False,
            duplicate_reason="content_hash",
        )
    
    # Upload file to object storage
    blob_uri = upload_file(
        file_bytes=file_bytes,
        filename=filename,
        content_hash=content_hash,
    )
    
    # Build parsed_data JSONB
    parsed_data_dict = _build_parsed_data(parsed_data)
    
    # Determine parse status based on confidence
    if parsed_data.confidence >= 0.8:
        parse_status = "success"
    elif parsed_data.confidence >= 0.5:
        parse_status = "partial"
    else:
        parse_status = "low_confidence"
    
    # Create receipt record
    receipt = Receipt(
        expense_id=expense_id,
        blob_uri=blob_uri,
        content_hash=content_hash,
        parsed_data=parsed_data_dict,
        raw_text=parsed_data.raw_text,
        raw_markdown=parsed_data.raw_markdown,
        ocr_provider=ocr_provider,
        ocr_confidence=parsed_data.confidence,
        parse_status=parse_status,
        file_type=file_type,
        file_size_bytes=len(file_bytes),
    )
    
    session.add(receipt)
    session.flush()  # Get the ID without committing
    
    logger.info(
        "receipt_created",
        receipt_id=str(receipt.id),
        expense_id=str(expense_id),
        blob_uri=blob_uri,
        hash=content_hash[:16],
        parse_status=parse_status,
        confidence=parsed_data.confidence,
    )
    
    return ReceiptWriteResult(receipt=receipt, created=True)


def get_receipt_by_expense_id(session: Session, expense_id: UUID) -> Receipt | None:
    """
    Get receipt by expense ID.
    
    Args:
        session: Database session
        expense_id: Expense ID
        
    Returns:
        Receipt object or None if not found
    """
    return session.query(Receipt).filter(Receipt.expense_id == expense_id).first()


def get_receipt_by_hash(session: Session, content_hash: str) -> Receipt | None:
    """
    Get receipt by content hash.
    
    Args:
        session: Database session
        content_hash: SHA256 hash of the file content
        
    Returns:
        Receipt object or None if not found
    """
    return session.query(Receipt).filter(Receipt.content_hash == content_hash).first()


def update_receipt_parse_status(
    session: Session,
    receipt_id: UUID,
    parse_status: str,
    parsed_data: dict | None = None,
) -> Receipt:
    """
    Update receipt parse status and optionally the parsed data.
    
    Args:
        session: Database session
        receipt_id: Receipt ID to update
        parse_status: New parse status (success, partial, failed)
        parsed_data: Optional updated parsed data
        
    Returns:
        Updated Receipt object
        
    Raises:
        ValueError: If receipt not found
    """
    receipt = session.query(Receipt).filter(Receipt.id == receipt_id).first()
    
    if not receipt:
        logger.error("receipt_not_found", receipt_id=str(receipt_id))
        raise ValueError(f"Receipt not found: {receipt_id}")
    
    old_status = receipt.parse_status
    receipt.parse_status = parse_status
    
    if parsed_data is not None:
        receipt.parsed_data = parsed_data
    
    session.flush()
    
    logger.info(
        "receipt_status_updated",
        receipt_id=str(receipt_id),
        old_status=old_status,
        new_status=parse_status,
    )
    
    return receipt





