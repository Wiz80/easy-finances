"""
Manual test script for text expense extractor.
Run this script to test the text extractor with various inputs.

Usage:
    python tests-manual/test_text_extractor.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.tools.extraction.text_extractor import extract_expense_from_text

# Configure logging
configure_logging()
logger = get_logger(__name__)


def test_case(description: str, text: str) -> None:
    """Run a single test case and print results."""
    print(f"\n{'='*80}")
    print(f"Test: {description}")
    print(f"{'='*80}")
    print(f"Input: {text}")
    print("-" * 80)
    
    try:
        result = extract_expense_from_text(text)
        
        print(f"✅ Extraction successful!")
        print(f"\nExtracted Data:")
        print(f"  Amount:      {result.amount} {result.currency}")
        print(f"  Description: {result.description}")
        print(f"  Category:    {result.category_candidate}")
        print(f"  Method:      {result.method}")
        print(f"  Merchant:    {result.merchant or 'N/A'}")
        print(f"  Card Hint:   {result.card_hint or 'N/A'}")
        print(f"  Confidence:  {result.confidence:.2f}")
        
        if result.notes:
            print(f"  Notes:       {result.notes}")
        
        return result
    
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        logger.error("test_case_failed", description=description, error=str(e))
        return None


def main() -> None:
    """Run all test cases."""
    print("\n" + "="*80)
    print(" TEXT EXPENSE EXTRACTOR - MANUAL TESTS")
    print("="*80)
    print(f"\nLLM Provider: {settings.llm_provider}")
    print(f"API Key configured: {'✓' if settings.openai_api_key else '✗'}")
    
    # Test cases covering different scenarios
    test_cases = [
        # Spanish input with card
        (
            "Spanish with card",
            "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa"
        ),
        
        # English input with cash
        (
            "English with cash",
            "Twenty soles for taxi, paid cash"
        ),
        
        # Delivery service
        (
            "Delivery service",
            "Pedí comida por Uber Eats, 35 soles"
        ),
        
        # Groceries
        (
            "Groceries shopping",
            "Compras del supermercado, 120 pesos mexicanos en efectivo"
        ),
        
        # Restaurant with card details
        (
            "Restaurant with card",
            "Dinner at Italian restaurant 85 USD, paid with Mastercard ending in 4532"
        ),
        
        # Hotel booking
        (
            "Hotel accommodation",
            "Hotel for 3 nights in Lima, 450 soles, tarjeta de crédito"
        ),
        
        # Transport - Uber
        (
            "Uber ride",
            "Uber to airport 25 dollars"
        ),
        
        # Tourism activity
        (
            "Museum entrance",
            "Entrada al museo 15 euros en efectivo"
        ),
        
        # Healthcare
        (
            "Pharmacy purchase",
            "Compré medicinas en la farmacia, 80 pesos"
        ),
        
        # Ambiguous/minimal info
        (
            "Minimal information",
            "Gasté 50"
        ),
        
        # Multiple items mentioned
        (
            "Multiple items",
            "Compré pan, leche y huevos por 25 soles en el mercado"
        ),
        
        # Transfer payment
        (
            "Bank transfer",
            "Transferencia de 200 dólares para el alquiler"
        ),
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for description, text in test_cases:
        result = test_case(description, text)
        results.append((description, text, result))
        
        if result:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(" SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests:  {len(test_cases)}")
    print(f"✅ Passed:    {passed}")
    print(f"❌ Failed:    {failed}")
    print(f"Success rate: {(passed/len(test_cases)*100):.1f}%")
    
    # Confidence distribution
    if results:
        confidences = [r[2].confidence for r in results if r[2] is not None]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
            
            print(f"\nConfidence Scores:")
            print(f"  Average: {avg_confidence:.2f}")
            print(f"  Min:     {min_confidence:.2f}")
            print(f"  Max:     {max_confidence:.2f}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

