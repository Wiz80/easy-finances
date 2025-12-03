import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

from app.tools.extraction.receipt_parser import extract_receipt_from_file
from app.config import settings

def test_llamaparse_extraction():
    # Load env vars
    load_dotenv()
    
    # Check keys
    if not os.getenv("LLAMAPARSE_API_KEY"):
        print("❌ LLAMAPARSE_API_KEY not found in env")
        return
        
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in env")
        return
        
    # Path to sample receipts
    base_dir = Path(__file__).parent.parent
    receipts_dir = base_dir / "tests/fixtures/transactions"
    
    if not receipts_dir.exists():
        print(f"❌ Receipts directory not found at {receipts_dir}")
        return

    # Get all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
    receipt_files = [
        f for f in receipts_dir.iterdir() 
        if f.name == "nequi.jpeg"
    ]
    
    if not receipt_files:
        print(f"❌ No receipt files found in {receipts_dir}")
        return

    print(f"🚀 Found {len(receipt_files)} receipts to test.")
    
    for receipt_file in receipt_files:
        print(f"\n\n🚀 Testing extraction for: {receipt_file.name}")
        print("=" * 60)
        
        try:
            receipt = extract_receipt_from_file(receipt_file)
            
            print("✅ Extraction Successful!")
            print("-" * 50)
            print(f"Merchant: {receipt.merchant}")
            print(f"Amount:   {receipt.total_amount} {receipt.currency}")
            print(f"Date:     {receipt.occurred_at}")
            print(f"Category: {receipt.category_candidate}")
            print(f"Confidence: {receipt.confidence}")
            print("-" * 50)
            print("Line Items:")
            for item in receipt.line_items:
                print(f" - {item.description}: {item.amount}")
            print("-" * 50)
            if receipt_file.name == "nequi.jpeg":
                print("RAW MARKDOWN PREVIEW:")
                print(receipt.raw_markdown)
                print("-" * 50)
            
        except Exception as e:
            print(f"❌ Extraction Failed for {receipt_file.name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_llamaparse_extraction()
