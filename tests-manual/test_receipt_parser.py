"""
Manual test script for receipt parser.
Tests receipt extraction with LlamaExtract API.

Usage:
    # Test with sample receipts (if available)
    python tests-manual/test_receipt_parser.py
    
    # Test with your own receipt
    python tests-manual/test_receipt_parser.py path/to/receipt.jpg
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.tools.extraction.receipt_parser import extract_receipt_from_file

# Configure logging
configure_logging()
logger = get_logger(__name__)


def test_receipt(receipt_path: Path, description: str = "") -> None:
    """Test receipt extraction and print results."""
    print(f"\n{'='*80}")
    print(f"RECEIPT EXTRACTION TEST")
    if description:
        print(f"Test: {description}")
    print(f"{'='*80}")
    print(f"File: {receipt_path.name}")
    print(f"Size: {receipt_path.stat().st_size:,} bytes")
    print("-" * 80)
    
    try:
        result = extract_receipt_from_file(receipt_path)
        
        print(f"✅ Extraction successful!")
        print(f"\nExtracted Data:")
        print(f"  Merchant:     {result.merchant}")
        print(f"  Amount:       {result.total_amount} {result.currency}")
        print(f"  Category:     {result.category_candidate}")
        print(f"  Date:         {result.occurred_at or 'N/A'}")
        print(f"  Receipt #:    {result.receipt_number or 'N/A'}")
        print(f"  Payment:      {result.payment_method or 'N/A'}")
        print(f"  Confidence:   {result.confidence:.2f}")
        
        if result.tax_amount:
            print(f"  Tax:          {result.tax_amount}")
        if result.tip_amount:
            print(f"  Tip:          {result.tip_amount}")
        
        if result.line_items:
            print(f"\n  Line Items ({len(result.line_items)}):")
            for idx, item in enumerate(result.line_items[:10], 1):  # Show first 10
                qty_str = f"{item.quantity}x " if item.quantity else ""
                print(f"    {idx}. {qty_str}{item.description}: {item.amount}")
            
            if len(result.line_items) > 10:
                print(f"    ... and {len(result.line_items) - 10} more items")
        
        return result
    
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        logger.error("receipt_test_failed", file=str(receipt_path), error=str(e))
        return None


def test_with_sample_receipts() -> None:
    """Test with sample receipts in fixtures."""
    receipts_dir = project_root / "tests" / "fixtures" / "receipts"
    
    if not receipts_dir.exists():
        print(f"\n⚠️  Receipts fixtures directory not found: {receipts_dir}")
        print("\nTo test the receipt parser:")
        print("1. Create directory: mkdir -p tests/fixtures/receipts")
        print("2. Add sample receipt images (.jpg, .png, .pdf)")
        print("3. Run this script again")
        print("\nOr test with your own file:")
        print("    python tests-manual/test_receipt_parser.py path/to/receipt.jpg")
        return
    
    # Find receipt files
    receipt_files = (
        list(receipts_dir.glob("*.jpg")) +
        list(receipts_dir.glob("*.jpeg")) +
        list(receipts_dir.glob("*.png")) +
        list(receipts_dir.glob("*.pdf"))
    )
    
    if not receipt_files:
        print(f"\n⚠️  No receipt files found in: {receipts_dir}")
        print("Supported formats: .jpg, .jpeg, .png, .pdf")
        return
    
    print(f"\n📁 Found {len(receipt_files)} receipt file(s)")
    
    results = []
    passed = 0
    failed = 0
    
    for receipt_file in sorted(receipt_files):
        result = test_receipt(receipt_file)
        results.append((receipt_file.name, result))
        
        if result:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(" SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests:  {len(receipt_files)}")
    print(f"✅ Passed:    {passed}")
    print(f"❌ Failed:    {failed}")
    print(f"Success rate: {(passed/len(receipt_files)*100):.1f}%")
    
    # Stats
    if results:
        confidences = [r[1].confidence for r in results if r[1] is not None]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
            
            print(f"\nConfidence Scores:")
            print(f"  Average: {avg_confidence:.2f}")
            print(f"  Min:     {min_confidence:.2f}")
            print(f"  Max:     {max_confidence:.2f}")
        
        # Category distribution
        categories = {}
        for _, result in results:
            if result:
                cat = result.category_candidate
                categories[cat] = categories.get(cat, 0) + 1
        
        if categories:
            print(f"\nCategory Distribution:")
            for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                print(f"  {cat}: {count}")
    
    print("\n" + "="*80)


def test_with_custom_file(file_path: str) -> None:
    """Test with custom file provided by user."""
    receipt_path = Path(file_path)
    
    if not receipt_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"\n📁 Testing custom receipt: {receipt_path.name}")
    test_receipt(receipt_path, description="Custom Receipt")


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print(" RECEIPT PARSER - MANUAL TESTS")
    print("="*80)
    print(f"\nLlamaExtract API Key configured: {'✓' if settings.llamaparse_api_key else '✗'}")
    
    if not settings.llamaparse_api_key:
        print("\n❌ LLAMAPARSE_API_KEY not configured in .env")
        print("This key is required for LlamaExtract API")
        return
    
    # Check if custom file provided
    if len(sys.argv) > 1:
        custom_file = sys.argv[1]
        test_with_custom_file(custom_file)
    else:
        # Test with sample receipts
        test_with_sample_receipts()


if __name__ == "__main__":
    main()


