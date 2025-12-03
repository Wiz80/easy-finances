#!/usr/bin/env python3
"""
Manual test script for storage layer (expense_writer and receipt_writer).

This script tests:
1. Expense creation with idempotency
2. Receipt creation with content hash deduplication
3. Category mapping fallback to 'misc'

Usage:
    # Ensure PostgreSQL is running via docker-compose
    docker-compose up -d postgres
    
    # Run migrations if needed
    alembic upgrade head
    
    # Run the test
    python tests-manual/test_storage_writers.py

Note: This test creates real database records. Use a test database or clean up after.
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal, engine
from app.logging_config import configure_logging, get_logger
from app.models.account import Account
from app.models.category import Category
from app.models.user import User
from app.schemas.extraction import ExtractedExpense, ExtractedReceipt, LineItem
from app.storage import (
    ExpenseWriteResult,
    ReceiptWriteResult,
    create_expense,
    create_receipt,
    get_expense_by_id,
    get_pending_expenses,
    get_receipt_by_expense_id,
    get_receipt_by_hash,
    compute_file_hash,
)

# Configure logging
configure_logging()
logger = get_logger(__name__)


def get_or_create_test_user(session) -> User:
    """Get or create a test user."""
    test_email = "test_storage@example.com"
    user = session.query(User).filter(User.email == test_email).first()
    
    if not user:
        user = User(
            id=uuid4(),
            email=test_email,
            full_name="Storage Test User",
            phone_number="+1234567890",
            home_currency="USD",
        )
        session.add(user)
        session.flush()
        logger.info("test_user_created", user_id=str(user.id))
    
    return user


def get_or_create_test_account(session, user: User) -> Account:
    """Get or create a test account."""
    account = session.query(Account).filter(
        Account.user_id == user.id,
        Account.name == "Test Account"
    ).first()
    
    if not account:
        account = Account(
            id=uuid4(),
            user_id=user.id,
            name="Test Account",
            account_type="checking",
            currency="USD",
        )
        session.add(account)
        session.flush()
        logger.info("test_account_created", account_id=str(account.id))
    
    return account


def test_expense_creation(session, user: User, account: Account) -> None:
    """Test expense creation with idempotency."""
    print("\n" + "=" * 60)
    print("TEST 1: Expense Creation with Idempotency")
    print("=" * 60)
    
    # Create an extracted expense
    extracted = ExtractedExpense(
        amount=Decimal("45.50"),
        currency="USD",
        description="Test expense - groceries at Whole Foods",
        category_candidate="in_house_food",
        method="card",
        merchant="Whole Foods",
        card_hint="Visa",
        confidence=0.92,
        raw_input="Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa",
    )
    
    msg_id = f"test_msg_{uuid4().hex[:8]}"
    
    # First creation - should succeed
    result1: ExpenseWriteResult = create_expense(
        session=session,
        extracted=extracted,
        user_id=user.id,
        account_id=account.id,
        source_type="text",
        msg_id=msg_id,
    )
    
    print(f"\n✅ First creation:")
    print(f"   Expense ID: {result1.expense.id}")
    print(f"   Created: {result1.created}")
    print(f"   Amount: {result1.expense.amount_original} {result1.expense.currency_original}")
    print(f"   Category ID: {result1.expense.category_id}")
    print(f"   Status: {result1.expense.status}")
    
    assert result1.created, "First expense should be created"
    
    # Attempt duplicate creation with same msg_id
    result2: ExpenseWriteResult = create_expense(
        session=session,
        extracted=extracted,
        user_id=user.id,
        account_id=account.id,
        source_type="text",
        msg_id=msg_id,
    )
    
    print(f"\n✅ Duplicate attempt (same msg_id):")
    print(f"   Expense ID: {result2.expense.id}")
    print(f"   Created: {result2.created}")
    print(f"   Duplicate Reason: {result2.duplicate_reason}")
    
    assert not result2.created, "Duplicate should not be created"
    assert result2.duplicate_reason == "msg_id", "Reason should be msg_id"
    assert result2.expense.id == result1.expense.id, "Should return same expense"
    
    # Verify expense retrieval
    fetched = get_expense_by_id(session, result1.expense.id)
    assert fetched is not None, "Expense should be retrievable"
    print(f"\n✅ Expense retrieval verified")
    
    # Test pending expenses
    pending = get_pending_expenses(session, user.id)
    assert len(pending) >= 1, "Should have at least one pending expense"
    print(f"   Found {len(pending)} pending expense(s)")


def test_category_fallback(session, user: User, account: Account) -> None:
    """Test category fallback to 'misc' for unknown categories."""
    print("\n" + "=" * 60)
    print("TEST 2: Category Fallback to 'misc'")
    print("=" * 60)
    
    # Create expense with unknown category
    extracted = ExtractedExpense(
        amount=Decimal("15.00"),
        currency="USD",
        description="Test expense with unknown category",
        category_candidate="unknown_category_xyz",  # Will be normalized to 'misc' by schema
        method="cash",
        confidence=0.75,
        raw_input="Test input",
    )
    
    result: ExpenseWriteResult = create_expense(
        session=session,
        extracted=extracted,
        user_id=user.id,
        account_id=account.id,
        source_type="text",
    )
    
    # Verify category was mapped to 'misc'
    category = session.query(Category).filter(
        Category.id == result.expense.category_id
    ).first()
    
    print(f"\n✅ Category fallback:")
    print(f"   Original candidate: 'unknown_category_xyz'")
    print(f"   Mapped to: '{category.slug}' ({category.name})")
    
    assert category.slug == "misc", "Should fallback to 'misc' category"


def test_receipt_creation(session, user: User, account: Account) -> None:
    """Test receipt creation with content hash deduplication."""
    print("\n" + "=" * 60)
    print("TEST 3: Receipt Creation with Deduplication")
    print("=" * 60)
    
    # First, create an expense to link the receipt to
    extracted_expense = ExtractedExpense(
        amount=Decimal("67.30"),
        currency="PEN",
        description="SuperMercado El Ahorro",
        category_candidate="in_house_food",
        method="cash",
        merchant="SuperMercado El Ahorro",
        confidence=0.88,
        raw_input="Receipt from SuperMercado",
    )
    
    expense_result = create_expense(
        session=session,
        extracted=extracted_expense,
        user_id=user.id,
        account_id=account.id,
        source_type="image",
    )
    
    # Create mock receipt file bytes (simulating an image)
    file_bytes = b"FAKE_IMAGE_DATA_FOR_TESTING_" + uuid4().bytes
    filename = "test_receipt.jpg"
    file_type = "image/jpeg"
    
    # Create extracted receipt data
    extracted_receipt = ExtractedReceipt(
        merchant="SuperMercado El Ahorro",
        total_amount=Decimal("67.30"),
        currency="PEN",
        occurred_at=datetime(2024, 11, 10, 14, 32, 0),
        line_items=[
            LineItem(description="Leche Gloria", amount=Decimal("12.50")),
            LineItem(description="Pan Integral", amount=Decimal("8.00")),
            LineItem(description="Otros items", amount=Decimal("46.80")),
        ],
        tax_amount=Decimal("5.50"),
        category_candidate="in_house_food",
        confidence=0.88,
        raw_text="SuperMercado El Ahorro\nLeche Gloria 12.50\nPan Integral 8.00\n...",
        raw_markdown="# Receipt\n## SuperMercado El Ahorro\n...",
    )
    
    # First creation - should succeed
    result1: ReceiptWriteResult = create_receipt(
        session=session,
        expense_id=expense_result.expense.id,
        file_bytes=file_bytes,
        filename=filename,
        parsed_data=extracted_receipt,
        file_type=file_type,
    )
    
    print(f"\n✅ First receipt creation:")
    print(f"   Receipt ID: {result1.receipt.id}")
    print(f"   Created: {result1.created}")
    print(f"   Expense ID: {result1.receipt.expense_id}")
    print(f"   Parse Status: {result1.receipt.parse_status}")
    print(f"   OCR Confidence: {result1.receipt.ocr_confidence}")
    print(f"   Content Hash: {result1.receipt.content_hash[:16]}...")
    
    assert result1.created, "First receipt should be created"
    
    # Attempt duplicate creation with same file bytes
    result2: ReceiptWriteResult = create_receipt(
        session=session,
        expense_id=expense_result.expense.id,  # Same expense
        file_bytes=file_bytes,  # Same file
        filename=filename,
        parsed_data=extracted_receipt,
        file_type=file_type,
    )
    
    print(f"\n✅ Duplicate attempt (same content hash):")
    print(f"   Receipt ID: {result2.receipt.id}")
    print(f"   Created: {result2.created}")
    print(f"   Duplicate Reason: {result2.duplicate_reason}")
    
    assert not result2.created, "Duplicate should not be created"
    assert result2.duplicate_reason == "content_hash", "Reason should be content_hash"
    assert result2.receipt.id == result1.receipt.id, "Should return same receipt"
    
    # Verify receipt retrieval by expense_id
    fetched_by_expense = get_receipt_by_expense_id(session, expense_result.expense.id)
    assert fetched_by_expense is not None, "Receipt should be retrievable by expense_id"
    print(f"\n✅ Receipt retrieval by expense_id verified")
    
    # Verify receipt retrieval by hash
    content_hash = compute_file_hash(file_bytes)
    fetched_by_hash = get_receipt_by_hash(session, content_hash)
    assert fetched_by_hash is not None, "Receipt should be retrievable by hash"
    print(f"✅ Receipt retrieval by content_hash verified")


def run_all_tests():
    """Run all storage layer tests."""
    print("\n" + "=" * 60)
    print("STORAGE LAYER TESTS")
    print("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Setup test data
        user = get_or_create_test_user(session)
        account = get_or_create_test_account(session, user)
        session.commit()
        
        # Run tests
        test_expense_creation(session, user, account)
        session.commit()
        
        test_category_fallback(session, user, account)
        session.commit()
        
        test_receipt_creation(session, user, account)
        session.commit()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        session.rollback()
        logger.error("test_failed", error=str(e), exc_info=True)
        print(f"\n❌ TEST FAILED: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_all_tests()

