"""
Storage layer for persisting expense and receipt data.

This module provides:
- Expense writer with idempotency (via msg_id or content hash)
- Receipt writer with deduplication (via SHA256 hash)
- Category mapping utilities
- Object storage utilities for receipt files
"""

from app.storage.category_mapper import (
    get_category_by_slug,
    get_default_category,
    map_category_candidate,
)
from app.storage.expense_writer import (
    ExpenseWriteResult,
    create_expense,
    get_expense_by_id,
    get_pending_expenses,
    update_expense_status,
)
from app.storage.object_storage import (
    compute_file_hash,
    delete_file,
    file_exists,
    get_file,
    get_file_url,
    get_minio_client,
    upload_file,
)
from app.storage.receipt_writer import (
    ReceiptWriteResult,
    create_receipt,
    get_receipt_by_expense_id,
    get_receipt_by_hash,
    update_receipt_parse_status,
)

__all__ = [
    # Category mapper
    "get_category_by_slug",
    "get_default_category",
    "map_category_candidate",
    # Expense writer
    "ExpenseWriteResult",
    "create_expense",
    "get_expense_by_id",
    "get_pending_expenses",
    "update_expense_status",
    # Object storage (MinIO)
    "compute_file_hash",
    "delete_file",
    "file_exists",
    "get_file",
    "get_file_url",
    "get_minio_client",
    "upload_file",
    # Receipt writer
    "ReceiptWriteResult",
    "create_receipt",
    "get_receipt_by_expense_id",
    "get_receipt_by_hash",
    "update_receipt_parse_status",
]

