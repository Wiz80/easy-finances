"""
Helper script to generate synthetic audio files for testing.
Uses text-to-speech to create audio test cases.

Usage:
    python tests-manual/generate_test_audio.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def generate_audio_files() -> None:
    """
    Generate test audio files using OpenAI TTS API.
    Creates various expense scenarios in different languages.
    """
    try:
        from openai import OpenAI
        from app.config import settings
        
        if not settings.openai_api_key:
            print("❌ OPENAI_API_KEY not configured")
            return
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Create output directory
        output_dir = project_root / "tests" / "fixtures" / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test cases to generate
        test_cases = [
            ("spanish_taxi.mp3", "Gasté veinte soles en taxi, pagué en efectivo", "nova", "es"),
            ("english_restaurant.mp3", "Dinner at Italian restaurant, eighty five dollars with my Visa card", "nova", "en"),
            ("spanish_delivery.mp3", "Pedí comida por Uber Eats, treinta y cinco soles", "nova", "es"),
            ("spanish_groceries.mp3", "Compras del supermercado, ciento veinte pesos mexicanos", "nova", "es"),
            ("english_hotel.mp3", "Hotel for three nights in Lima, four hundred fifty soles", "nova", "en"),
        ]
        
        print("\n🎤 Generating test audio files...")
        print(f"Output directory: {output_dir}\n")
        
        for filename, text, voice, language in test_cases:
            output_path = output_dir / filename
            
            print(f"Generating: {filename}")
            print(f"  Text: {text}")
            print(f"  Voice: {voice}, Language: {language}")
            
            try:
                response = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                )
                
                # Save to file
                response.stream_to_file(output_path)
                
                file_size = output_path.stat().st_size
                print(f"  ✅ Saved: {output_path.name} ({file_size:,} bytes)\n")
                
            except Exception as e:
                print(f"  ❌ Failed: {e}\n")
                logger.error("audio_generation_failed", filename=filename, error=str(e))
        
        print(f"✅ Audio generation complete!")
        print(f"Generated files in: {output_dir}")
        print(f"\nYou can now run: python tests-manual/test_audio_extractor.py")
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Make sure OpenAI SDK is installed: uv pip install openai")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error("audio_generation_error", error=str(e), exc_info=True)


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print(" TEST AUDIO GENERATOR")
    print("="*80)
    print("\nThis script generates synthetic audio files for testing.")
    print("It uses OpenAI's TTS API to create realistic voice samples.\n")
    
    response = input("Generate test audio files? (y/n): ").strip().lower()
    
    if response == 'y':
        generate_audio_files()
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()


