"""
Storage layer for persisting data.

This module provides:
- Expense writer with idempotency (via msg_id or content hash)
- Receipt writer with deduplication (via SHA256 hash)
- Category mapping utilities
- Object storage utilities for receipt files
- User writer for user configuration
- Trip writer for trip management
- Budget writer for budget allocations
- Card writer for card/account management
- Conversation manager for chat state
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
from app.storage.user_writer import (
    UserWriteResult,
    create_user,
    get_user_by_id,
    get_user_by_phone,
    update_user,
    complete_onboarding,
    set_onboarding_step,
    activate_travel_mode,
    deactivate_travel_mode,
)
from app.storage.trip_writer import (
    TripWriteResult,
    create_trip,
    get_trip_by_id,
    get_user_trips,
    get_current_trip,
    update_trip,
    complete_trip,
    cancel_trip,
    get_country_info,
)
from app.storage.budget_writer import (
    BudgetWriteResult,
    create_budget,
    create_budget_from_flow_data,
    get_budget_by_id,
    get_user_budgets,
    get_active_budget_for_trip,
    add_allocation,
    update_allocation_spent,
    add_funding_source,
    get_budget_summary,
)
from app.storage.card_writer import (
    CardWriteResult,
    AccountWriteResult,
    create_card,
    create_card_for_user,
    create_card_from_flow_data,
    create_account,
    get_card_by_id,
    get_account_by_id,
    get_user_cards,
    get_user_accounts,
    get_default_account,
    get_default_card,
    update_card,
    deactivate_card,
    set_default_card,
)
from app.storage.conversation_manager import (
    ConversationResult,
    create_conversation,
    get_conversation_by_id,
    get_active_conversation,
    get_user_conversations,
    update_conversation,
    update_conversation_state_data,
    set_pending_confirmation,
    clear_pending_confirmation,
    complete_conversation,
    cancel_conversation,
    expire_conversation,
    cleanup_expired_conversations,
    get_conversation_summary,
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
    # User writer
    "UserWriteResult",
    "create_user",
    "get_user_by_id",
    "get_user_by_phone",
    "update_user",
    "complete_onboarding",
    "set_onboarding_step",
    "activate_travel_mode",
    "deactivate_travel_mode",
    # Trip writer
    "TripWriteResult",
    "create_trip",
    "get_trip_by_id",
    "get_user_trips",
    "get_current_trip",
    "update_trip",
    "complete_trip",
    "cancel_trip",
    "get_country_info",
    # Budget writer
    "BudgetWriteResult",
    "create_budget",
    "create_budget_from_flow_data",
    "get_budget_by_id",
    "get_user_budgets",
    "get_active_budget_for_trip",
    "add_allocation",
    "update_allocation_spent",
    "add_funding_source",
    "get_budget_summary",
    # Card writer
    "CardWriteResult",
    "AccountWriteResult",
    "create_card",
    "create_card_for_user",
    "create_card_from_flow_data",
    "create_account",
    "get_card_by_id",
    "get_account_by_id",
    "get_user_cards",
    "get_user_accounts",
    "get_default_account",
    "get_default_card",
    "update_card",
    "deactivate_card",
    "set_default_card",
    # Conversation manager
    "ConversationResult",
    "create_conversation",
    "get_conversation_by_id",
    "get_active_conversation",
    "get_user_conversations",
    "update_conversation",
    "update_conversation_state_data",
    "set_pending_confirmation",
    "clear_pending_confirmation",
    "complete_conversation",
    "cancel_conversation",
    "expire_conversation",
    "cleanup_expired_conversations",
    "get_conversation_summary",
]

