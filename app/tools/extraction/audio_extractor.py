"""
Audio expense extractor using OpenAI Whisper API.
Transcribes audio to text, then extracts expense information.
"""

import hashlib
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings
from app.logging_config import get_logger
from app.schemas.extraction import ExtractedExpense
from app.tools.extraction.text_extractor import extract_expense_from_text

logger = get_logger(__name__)


def transcribe_audio(
    audio_file: str | Path | bytes,
    language: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Transcribe audio file using OpenAI Whisper API.
    
    Args:
        audio_file: Path to audio file or audio bytes
        language: Optional language code (e.g., 'es', 'en'). Auto-detect if None.
        **kwargs: Additional context for logging
        
    Returns:
        dict with 'text' (transcription) and 'language' (detected)
        
    Raises:
        ValueError: If API key not configured or file invalid
        Exception: If API call fails
        
    Example:
        >>> result = transcribe_audio("audio.ogg")
        >>> print(result['text'])
        "Gasté veinte soles en taxi"
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    logger.info(
        "transcribing_audio",
        audio_type=type(audio_file).__name__,
        language=language or "auto",
        **kwargs,
    )
    
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Handle different input types
        if isinstance(audio_file, bytes):
            # Create a temporary file-like object from bytes
            import io
            audio_data = io.BytesIO(audio_file)
            audio_data.name = "audio.ogg"  # Whisper API needs a filename
            file_to_transcribe = audio_data
            
            # Calculate hash for logging
            audio_hash = hashlib.sha256(audio_file).hexdigest()[:16]
            logger.debug("audio_from_bytes", size=len(audio_file), hash=audio_hash)
        else:
            # File path
            audio_path = Path(audio_file)
            if not audio_path.exists():
                raise ValueError(f"Audio file not found: {audio_file}")
            
            file_to_transcribe = open(audio_path, "rb")
            logger.debug("audio_from_file", path=str(audio_path), size=audio_path.stat().st_size)
        
        # Call Whisper API
        logger.debug("calling_whisper_api", model=settings.whisper_model)
        
        transcription = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=file_to_transcribe,
            language=language,  # None for auto-detect
            response_format="verbose_json",  # Get detailed response with language
        )
        
        # Close file if we opened it
        if not isinstance(audio_file, bytes):
            file_to_transcribe.close()
        
        result = {
            "text": transcription.text,
            "language": transcription.language if hasattr(transcription, "language") else None,
            "duration": transcription.duration if hasattr(transcription, "duration") else None,
        }
        
        logger.info(
            "audio_transcribed_successfully",
            text_length=len(result["text"]),
            language=result["language"],
            duration=result.get("duration"),
            **kwargs,
        )
        
        return result
    
    except Exception as e:
        logger.error(
            "audio_transcription_failed",
            error=str(e),
            error_type=type(e).__name__,
            **kwargs,
            exc_info=True,
        )
        raise


def extract_expense_from_audio(
    audio_file: str | Path | bytes,
    language: str | None = None,
    **kwargs: Any,
) -> ExtractedExpense:
    """
    Extract structured expense data from audio file.
    
    Pipeline:
    1. Transcribe audio using OpenAI Whisper API
    2. Extract expense data from transcription using Text Extractor
    3. Combine confidence scores (ASR + extraction)
    4. Store transcription and metadata in source_meta
    
    Args:
        audio_file: Path to audio file or audio bytes
        language: Optional language code for transcription
        **kwargs: Additional context (e.g., user_id, request_id) for logging
        
    Returns:
        ExtractedExpense with audio metadata in raw_input
        
    Raises:
        ValueError: If audio file invalid or empty transcription
        
    Example:
        >>> expense = extract_expense_from_audio("voice_note.ogg")
        >>> print(f"{expense.amount} {expense.currency} - {expense.description}")
        20 PEN - taxi
    """
    logger.info("extracting_expense_from_audio", **kwargs)
    
    # Step 1: Transcribe audio
    transcription_result = transcribe_audio(audio_file, language=language, **kwargs)
    
    text = transcription_result["text"].strip()
    
    if not text:
        raise ValueError("Transcription resulted in empty text")
    
    logger.debug(
        "transcription_result",
        text=text,
        text_length=len(text),
        language=transcription_result.get("language"),
        **kwargs,
    )
    
    # Step 2: Extract expense from transcribed text
    try:
        expense = extract_expense_from_text(text, **kwargs)
        
        # Step 3: Adjust confidence based on ASR quality
        # Whisper is generally very accurate, but we can still factor it in
        # For now, we'll use a high base confidence for Whisper API (0.95)
        # and combine it with extraction confidence
        
        whisper_confidence = 0.95  # High confidence for Whisper API
        extraction_confidence = expense.confidence
        
        # Weighted average: 30% ASR, 70% extraction
        combined_confidence = (whisper_confidence * 0.3) + (extraction_confidence * 0.7)
        expense.confidence = min(combined_confidence, 1.0)
        
        # Step 4: Store audio metadata in raw_input
        # Format: "[AUDIO] transcription: {text}"
        expense.raw_input = f"[AUDIO] {text}"
        
        # Add transcription metadata to notes if not already present
        if expense.notes:
            expense.notes = f"Transcription: {text}\n{expense.notes}"
        else:
            expense.notes = f"Transcription: {text}"
        
        logger.info(
            "expense_extracted_from_audio_successfully",
            amount=float(expense.amount),
            currency=expense.currency,
            category=expense.category_candidate,
            method=expense.method,
            confidence=expense.confidence,
            original_text_confidence=extraction_confidence,
            transcription_length=len(text),
            detected_language=transcription_result.get("language"),
            **kwargs,
        )
        
        return expense
    
    except Exception as e:
        logger.error(
            "expense_extraction_from_audio_failed",
            error=str(e),
            error_type=type(e).__name__,
            transcription=text,
            **kwargs,
            exc_info=True,
        )
        raise


# Alias for convenience
extract = extract_expense_from_audio
transcribe = transcribe_audio


