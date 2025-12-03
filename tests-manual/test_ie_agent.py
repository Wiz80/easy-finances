#!/usr/bin/env python3
"""
Manual test script for IE Agent (LangGraph-based expense extraction).

This script tests:
1. Text expense extraction
2. Audio expense extraction (if fixtures available)
3. Image/Receipt extraction (if fixtures available)
4. Idempotency (duplicate detection)
5. Error handling

Usage:
    # Ensure PostgreSQL and MinIO are running via docker-compose
    docker-compose up -d postgres minio
    
    # Run migrations if needed
    alembic upgrade head
    
    # Run the test
    python tests-manual/test_ie_agent.py

Note: Requires valid API keys in .env for OpenAI (Whisper, GPT-4) and LlamaParse.
"""

import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agents.ie_agent import process_expense, IEAgentResult
from app.database import SessionLocal
from app.logging_config import configure_logging, get_logger
from app.models.account import Account
from app.models.user import User

# Configure logging
configure_logging()
logger = get_logger(__name__)


def get_or_create_test_user(session) -> User:
    """Get or create a test user."""
    test_email = "test_ie_agent@example.com"
    user = session.query(User).filter(User.email == test_email).first()
    
    if not user:
        user = User(
            id=uuid4(),
            email=test_email,
            full_name="IE Agent Test User",
            phone_number="+1987654321",
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
        Account.name == "IE Agent Test Account"
    ).first()
    
    if not account:
        account = Account(
            id=uuid4(),
            user_id=user.id,
            name="IE Agent Test Account",
            account_type="checking",
            currency="USD",
        )
        session.add(account)
        session.flush()
        logger.info("test_account_created", account_id=str(account.id))
    
    return account


def test_text_extraction(user: User, account: Account) -> None:
    """Test expense extraction from plain text."""
    print("\n" + "=" * 60)
    print("TEST 1: Text Expense Extraction")
    print("=" * 60)
    
    test_cases = [
        {
            "input": "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa",
            "expected_currency": "USD",
            "expected_category": "in_house_food",
        },
        {
            "input": "Pagué 20 soles por el taxi al aeropuerto en efectivo",
            "expected_currency": "PEN",
            "expected_category": "transport",
        },
        {
            "input": "Hotel Marriott - 150 euros por noche, pagado con Mastercard",
            "expected_currency": "EUR",
            "expected_category": "lodging",
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Input: {test_case['input'][:60]}...")
        
        result = process_expense(
            user_id=user.id,
            account_id=account.id,
            raw_input=test_case["input"],
            input_type="text",
        )
        
        print(f"✅ Result: {result}")
        print(f"   Status: {result.status}")
        print(f"   Success: {result.success}")
        
        if result.success and result.extracted_expense:
            exp = result.extracted_expense
            print(f"   Amount: {exp.amount} {exp.currency}")
            print(f"   Category: {exp.category_candidate}")
            print(f"   Description: {exp.description}")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Expense ID: {result.expense_id}")
        
        if result.errors:
            print(f"   Errors: {result.errors}")


def test_idempotency(user: User, account: Account) -> None:
    """Test duplicate detection via msg_id."""
    print("\n" + "=" * 60)
    print("TEST 2: Idempotency (Duplicate Detection)")
    print("=" * 60)
    
    msg_id = f"test_msg_{uuid4().hex[:8]}"
    input_text = "30 soles en uber"
    
    # First submission
    print(f"\n--- First Submission (msg_id: {msg_id}) ---")
    result1 = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input=input_text,
        input_type="text",
        msg_id=msg_id,
    )
    
    print(f"✅ First: {result1}")
    print(f"   Created: {result1.expense_id}")
    print(f"   Is Duplicate: {result1.is_duplicate}")
    
    # Second submission with same msg_id
    print(f"\n--- Second Submission (same msg_id) ---")
    result2 = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input=input_text,
        input_type="text",
        msg_id=msg_id,
    )
    
    print(f"✅ Second: {result2}")
    print(f"   Returned: {result2.expense_id}")
    print(f"   Is Duplicate: {result2.is_duplicate}")
    
    # Verify same expense returned
    assert result1.expense_id == result2.expense_id, "Should return same expense"
    assert result2.is_duplicate, "Should be marked as duplicate"
    print(f"\n✅ Idempotency verified: Same expense returned for duplicate msg_id")


def test_audio_extraction(user: User, account: Account) -> None:
    """Test expense extraction from audio file."""
    print("\n" + "=" * 60)
    print("TEST 3: Audio Expense Extraction")
    print("=" * 60)
    
    # Check if audio fixtures exist
    audio_fixtures = list(Path("tests/fixtures/audio").glob("*.ogg")) + \
                     list(Path("tests/fixtures/audio").glob("*.mp3"))
    
    if not audio_fixtures:
        print("⚠️  No audio fixtures found in tests/fixtures/audio/")
        print("   Skipping audio extraction test")
        return
    
    audio_file = audio_fixtures[0]
    print(f"\nUsing audio file: {audio_file}")
    
    with open(audio_file, "rb") as f:
        audio_bytes = f.read()
    
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input=audio_bytes,
        input_type="audio",
        filename=audio_file.name,
        file_type="audio/ogg" if audio_file.suffix == ".ogg" else "audio/mpeg",
    )
    
    print(f"✅ Result: {result}")
    print(f"   Status: {result.status}")
    
    if result.success and result.extracted_expense:
        exp = result.extracted_expense
        print(f"   Amount: {exp.amount} {exp.currency}")
        print(f"   Description: {exp.description}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Expense ID: {result.expense_id}")
    
    if result.errors:
        print(f"   Errors: {result.errors}")


def test_image_extraction(user: User, account: Account) -> None:
    """Test expense extraction from receipt image."""
    print("\n" + "=" * 60)
    print("TEST 4: Image/Receipt Extraction")
    print("=" * 60)
    
    # Check if image fixtures exist
    image_fixtures = list(Path("tests/fixtures/bill").glob("*.jpeg")) + \
                     list(Path("tests/fixtures/bill").glob("*.jpg")) + \
                     list(Path("tests/fixtures/bill").glob("*.png"))
    
    if not image_fixtures:
        print("⚠️  No image fixtures found in tests/fixtures/bill/")
        print("   Skipping image extraction test")
        return
    
    image_file = image_fixtures[0]
    print(f"\nUsing image file: {image_file}")
    
    with open(image_file, "rb") as f:
        image_bytes = f.read()
    
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input=image_bytes,
        input_type="image",
        filename=image_file.name,
        file_type="image/jpeg",
    )
    
    print(f"✅ Result: {result}")
    print(f"   Status: {result.status}")
    
    if result.success:
        if result.extracted_expense:
            exp = result.extracted_expense
            print(f"   Amount: {exp.amount} {exp.currency}")
            print(f"   Merchant: {exp.merchant}")
            print(f"   Description: {exp.description}")
        
        if result.extracted_receipt:
            rec = result.extracted_receipt
            print(f"   Receipt Merchant: {rec.merchant}")
            print(f"   Line Items: {len(rec.line_items)}")
        
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Expense ID: {result.expense_id}")
        print(f"   Receipt ID: {result.receipt_id}")
    
    if result.errors:
        print(f"   Errors: {result.errors}")


def test_error_handling(user: User, account: Account) -> None:
    """Test error handling for invalid inputs."""
    print("\n" + "=" * 60)
    print("TEST 5: Error Handling")
    print("=" * 60)
    
    # Test with empty input
    print("\n--- Empty Input ---")
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input="",
        input_type="text",
    )
    
    print(f"✅ Result: {result}")
    print(f"   Status: {result.status}")
    print(f"   Errors: {result.errors}")
    
    assert result.status == "error", "Should be error status"
    print("   ✅ Empty input handled correctly")
    
    # Test with unknown input type
    print("\n--- Unknown Input Type ---")
    result = process_expense(
        user_id=user.id,
        account_id=account.id,
        raw_input=b"random bytes",
        input_type="unknown",
    )
    
    print(f"✅ Result: {result}")
    print(f"   Status: {result.status}")
    print(f"   Errors: {result.errors}")


def run_all_tests():
    """Run all IE Agent tests."""
    print("\n" + "=" * 60)
    print("IE AGENT TESTS (LangGraph)")
    print("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Setup test data
        user = get_or_create_test_user(session)
        account = get_or_create_test_account(session, user)
        session.commit()
        
        # Run tests
        test_text_extraction(user, account)
        test_idempotency(user, account)
        test_audio_extraction(user, account)
        test_image_extraction(user, account)
        test_error_handling(user, account)
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED!")
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

