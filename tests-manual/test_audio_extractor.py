"""
Manual test script for audio expense extractor.
Tests audio transcription with OpenAI Whisper API + expense extraction.

Usage:
    # Test with generated audio files
    python tests-manual/test_audio_extractor.py
    
    # Test with your own audio file
    python tests-manual/test_audio_extractor.py path/to/your/audio.ogg
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.tools.extraction.audio_extractor import (
    extract_expense_from_audio,
    transcribe_audio,
)

# Configure logging
configure_logging()
logger = get_logger(__name__)


def test_transcription_only(audio_file: Path) -> None:
    """Test only the transcription part."""
    print(f"\n{'='*80}")
    print(f"TRANSCRIPTION TEST")
    print(f"{'='*80}")
    print(f"Audio file: {audio_file.name}")
    print(f"Size: {audio_file.stat().st_size:,} bytes")
    print("-" * 80)
    
    try:
        result = transcribe_audio(audio_file)
        
        print(f"✅ Transcription successful!")
        print(f"\nTranscribed Text:")
        print(f"  {result['text']}")
        print(f"\nMetadata:")
        print(f"  Language: {result.get('language', 'N/A')}")
        print(f"  Duration: {result.get('duration', 'N/A')}s")
        
        return result
    
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        logger.error("transcription_test_failed", file=str(audio_file), error=str(e))
        return None


def test_expense_extraction(audio_file: Path, language: str | None = None) -> None:
    """Test full pipeline: transcription + extraction."""
    print(f"\n{'='*80}")
    print(f"EXPENSE EXTRACTION TEST")
    print(f"{'='*80}")
    print(f"Audio file: {audio_file.name}")
    print(f"Size: {audio_file.stat().st_size:,} bytes")
    if language:
        print(f"Language hint: {language}")
    print("-" * 80)
    
    try:
        result = extract_expense_from_audio(audio_file, language=language)
        
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
            print(f"\n  Notes:")
            for line in result.notes.split('\n'):
                print(f"    {line}")
        
        return result
    
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        logger.error("extraction_test_failed", file=str(audio_file), error=str(e))
        return None


def test_with_generated_files() -> None:
    """Run tests with pre-generated audio files."""
    audio_dir = project_root / "tests" / "fixtures" / "audio"
    
    if not audio_dir.exists():
        print(f"\n⚠️  Audio fixtures directory not found: {audio_dir}")
        print("Generate test files first with:")
        print("    python tests-manual/generate_test_audio.py")
        return
    
    # Find all audio files
    audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.ogg"))
    
    if not audio_files:
        print(f"\n⚠️  No audio files found in: {audio_dir}")
        print("Generate test files first with:")
        print("    python tests-manual/generate_test_audio.py")
        return
    
    print(f"\n📁 Found {len(audio_files)} audio file(s) in fixtures")
    
    results = []
    passed = 0
    failed = 0
    
    for audio_file in sorted(audio_files):
        # Test transcription first
        transcription = test_transcription_only(audio_file)
        
        # Then test full extraction
        result = test_expense_extraction(audio_file)
        
        results.append((audio_file.name, transcription, result))
        
        if result:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(" SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests:  {len(audio_files)}")
    print(f"✅ Passed:    {passed}")
    print(f"❌ Failed:    {failed}")
    print(f"Success rate: {(passed/len(audio_files)*100):.1f}%")
    
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


def test_with_custom_file(audio_path: str) -> None:
    """Test with a custom audio file provided by user."""
    audio_file = Path(audio_path)
    
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_path}")
        return
    
    print(f"\n📁 Testing custom audio file: {audio_file.name}")
    
    # Ask for language hint
    print("\nLanguage hint (optional):")
    print("  Press Enter for auto-detect")
    print("  Or enter language code: es, en, etc.")
    language = input("Language: ").strip() or None
    
    # Test transcription
    transcription = test_transcription_only(audio_file)
    
    # Test extraction
    if transcription:
        test_expense_extraction(audio_file, language=language)


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print(" AUDIO EXPENSE EXTRACTOR - MANUAL TESTS")
    print("="*80)
    print(f"\nWhisper Provider: {settings.whisper_provider}")
    print(f"Whisper Model: {settings.whisper_model}")
    print(f"OpenAI API Key configured: {'✓' if settings.openai_api_key else '✗'}")
    
    # Check if custom file provided as argument
    if len(sys.argv) > 1:
        custom_file = sys.argv[1]
        test_with_custom_file(custom_file)
    else:
        # Test with generated files
        test_with_generated_files()


if __name__ == "__main__":
    main()


