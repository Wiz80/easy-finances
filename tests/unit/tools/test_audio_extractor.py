"""
Unit tests for audio_extractor.py.

Tests:
- Audio transcription via Whisper API (mocked)
- Audio to expense extraction pipeline
- Different audio input types (file path, bytes)
- Confidence score combination
- Error handling
"""

import io
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from app.schemas.extraction import ExtractedExpense


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_transcription_response():
    """Create a mock transcription response from Whisper API."""
    response = MagicMock()
    response.text = "Gasté veinte soles en taxi"
    response.language = "es"
    response.duration = 3.5
    return response


@pytest.fixture
def mock_openai_client(mock_transcription_response):
    """Create a mock OpenAI client."""
    client = MagicMock()
    client.audio.transcriptions.create.return_value = mock_transcription_response
    return client


@pytest.fixture
def mock_extracted_expense():
    """Create a mock ExtractedExpense."""
    return ExtractedExpense(
        amount=Decimal("20"),
        currency="PEN",
        description="taxi",
        category_candidate="transport",
        method="cash",
        merchant=None,
        card_hint=None,
        occurred_at=None,
        notes=None,
        installments=1,
        category_confidence=0.9,
        category_source="llm",
        confidence=0.85,
        raw_input="Gasté veinte soles en taxi",
    )


@pytest.fixture
def audio_bytes():
    """Create mock audio bytes."""
    return b"\x00\x01\x02\x03\x04\x05" * 100


# ─────────────────────────────────────────────────────────────────────────────
# Transcription Tests - Input Validation
# ─────────────────────────────────────────────────────────────────────────────


class TestTranscriptionInputValidation:
    """Tests for input validation in transcribe_audio."""

    @patch("app.tools.extraction.audio_extractor.settings")
    def test_missing_api_key_raises(self, mock_settings):
        """Should raise ValueError when API key is missing."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = None
        
        with pytest.raises(ValueError) as exc_info:
            transcribe_audio("audio.ogg")
        
        assert "OPENAI_API_KEY not configured" in str(exc_info.value)

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_nonexistent_file_raises(self, mock_openai, mock_settings):
        """Should raise ValueError for non-existent audio file."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        
        with pytest.raises(ValueError) as exc_info:
            transcribe_audio("/nonexistent/path/audio.ogg")
        
        assert "Audio file not found" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# Transcription Tests - File Path Input
# ─────────────────────────────────────────────────────────────────────────────


class TestTranscriptionFromFile:
    """Tests for transcribing audio from file paths."""

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    @patch("builtins.open", mock_open(read_data=b"audio data"))
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_transcribe_from_file_path(
        self,
        mock_stat,
        mock_exists,
        mock_openai_class,
        mock_settings,
        mock_transcription_response,
    ):
        """Should transcribe audio from file path."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 1000
        mock_stat.return_value = mock_stat_result
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_transcription_response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio("test_audio.ogg")
        
        assert result["text"] == "Gasté veinte soles en taxi"
        assert result["language"] == "es"
        assert result["duration"] == 3.5

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    @patch("builtins.open", mock_open(read_data=b"audio data"))
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_transcribe_with_language_hint(
        self,
        mock_stat,
        mock_exists,
        mock_openai_class,
        mock_settings,
        mock_transcription_response,
    ):
        """Should pass language hint to Whisper API."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 1000
        mock_stat.return_value = mock_stat_result
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_transcription_response
        mock_openai_class.return_value = mock_client
        
        transcribe_audio("test_audio.ogg", language="es")
        
        # Verify language was passed to API
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["language"] == "es"


# ─────────────────────────────────────────────────────────────────────────────
# Transcription Tests - Bytes Input
# ─────────────────────────────────────────────────────────────────────────────


class TestTranscriptionFromBytes:
    """Tests for transcribing audio from bytes."""

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_transcribe_from_bytes(
        self,
        mock_openai_class,
        mock_settings,
        mock_transcription_response,
        audio_bytes,
    ):
        """Should transcribe audio from bytes."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_transcription_response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio(audio_bytes)
        
        assert result["text"] == "Gasté veinte soles en taxi"
        assert result["language"] == "es"

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_transcribe_bytes_uses_bytesio(
        self,
        mock_openai_class,
        mock_settings,
        mock_transcription_response,
        audio_bytes,
    ):
        """Should use BytesIO for bytes input."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_transcription_response
        mock_openai_class.return_value = mock_client
        
        transcribe_audio(audio_bytes)
        
        # Verify file was passed to API
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert "file" in call_kwargs


# ─────────────────────────────────────────────────────────────────────────────
# Expense Extraction from Audio Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExpenseExtractionFromAudio:
    """Tests for the complete audio-to-expense extraction pipeline."""

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_basic_audio_extraction(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should extract expense from audio via transcription."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "Gasté veinte soles en taxi",
            "language": "es",
            "duration": 3.5,
        }
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert result.amount == Decimal("20")
        assert result.currency == "PEN"
        assert result.category_candidate == "transport"
        assert "[AUDIO]" in result.raw_input

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_empty_transcription_raises(self, mock_extract_text, mock_transcribe):
        """Should raise ValueError for empty transcription."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "",
            "language": None,
            "duration": 0,
        }
        
        with pytest.raises(ValueError) as exc_info:
            extract_expense_from_audio("test_audio.ogg")
        
        assert "empty text" in str(exc_info.value).lower()

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_whitespace_transcription_raises(self, mock_extract_text, mock_transcribe):
        """Should raise ValueError for whitespace-only transcription."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "   \n\t  ",
            "language": None,
            "duration": 0,
        }
        
        with pytest.raises(ValueError) as exc_info:
            extract_expense_from_audio("test_audio.ogg")
        
        assert "empty text" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Confidence Score Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConfidenceScoring:
    """Tests for confidence score calculation in audio extraction."""

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_confidence_is_combined(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should combine Whisper and extraction confidence."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "Gasté veinte soles en taxi",
            "language": "es",
            "duration": 3.5,
        }
        
        # Set extraction confidence to 0.85
        mock_extracted_expense.confidence = 0.85
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        # Combined: (0.95 * 0.3) + (0.85 * 0.7) = 0.285 + 0.595 = 0.88
        expected_confidence = (0.95 * 0.3) + (0.85 * 0.7)
        assert result.confidence == pytest.approx(expected_confidence, rel=0.01)

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_confidence_capped_at_one(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should cap combined confidence at 1.0."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "Gasté veinte soles",
            "language": "es",
            "duration": 2.0,
        }
        
        # Set very high extraction confidence
        mock_extracted_expense.confidence = 1.0
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert result.confidence <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Raw Input and Notes Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRawInputAndNotes:
    """Tests for raw_input and notes fields in audio extraction."""

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_raw_input_includes_audio_marker(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should include [AUDIO] marker in raw_input."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        transcription = "Gasté cincuenta dólares en restaurante"
        mock_transcribe.return_value = {
            "text": transcription,
            "language": "es",
            "duration": 4.0,
        }
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert result.raw_input.startswith("[AUDIO]")
        assert transcription in result.raw_input

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_notes_includes_transcription(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should include transcription in notes."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        transcription = "Gasté cincuenta dólares"
        mock_transcribe.return_value = {
            "text": transcription,
            "language": "es",
            "duration": 3.0,
        }
        mock_extracted_expense.notes = None  # No existing notes
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert "Transcription:" in result.notes
        assert transcription in result.notes

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_notes_preserves_existing_notes(
        self,
        mock_extract_text,
        mock_transcribe,
        mock_extracted_expense,
    ):
        """Should preserve existing notes when adding transcription."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        transcription = "Gasté veinte soles"
        mock_transcribe.return_value = {
            "text": transcription,
            "language": "es",
            "duration": 2.0,
        }
        
        # Set existing notes
        mock_extracted_expense.notes = "Important note"
        mock_extract_text.return_value = mock_extracted_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert "Important note" in result.notes
        assert "Transcription:" in result.notes


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling in audio extraction."""

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    def test_transcription_error_propagates(self, mock_transcribe):
        """Should propagate transcription errors."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.side_effect = Exception("Whisper API Error")
        
        with pytest.raises(Exception) as exc_info:
            extract_expense_from_audio("test_audio.ogg")
        
        assert "Whisper API Error" in str(exc_info.value)

    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_extraction_error_propagates(self, mock_extract_text, mock_transcribe):
        """Should propagate text extraction errors."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": "Some transcription",
            "language": "es",
            "duration": 2.0,
        }
        mock_extract_text.side_effect = Exception("Extraction Error")
        
        with pytest.raises(Exception) as exc_info:
            extract_expense_from_audio("test_audio.ogg")
        
        assert "Extraction Error" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# Language Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLanguageDetection:
    """Tests for language detection in transcription."""

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_auto_detect_spanish(
        self,
        mock_openai_class,
        mock_settings,
    ):
        """Should auto-detect Spanish language."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        response = MagicMock()
        response.text = "Gasté veinte soles en taxi"
        response.language = "es"
        response.duration = 3.5
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio(b"audio bytes")
        
        assert result["language"] == "es"

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_auto_detect_english(
        self,
        mock_openai_class,
        mock_settings,
    ):
        """Should auto-detect English language."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        response = MagicMock()
        response.text = "Spent twenty dollars on taxi"
        response.language = "en"
        response.duration = 3.0
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio(b"audio bytes")
        
        assert result["language"] == "en"


# ─────────────────────────────────────────────────────────────────────────────
# Whisper API Response Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestWhisperAPIResponse:
    """Tests for handling various Whisper API responses."""

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_handles_response_without_duration(
        self,
        mock_openai_class,
        mock_settings,
    ):
        """Should handle response without duration field."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        response = MagicMock()
        response.text = "Test transcription"
        response.language = "en"
        # No duration attribute
        del response.duration
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio(b"audio bytes")
        
        assert result["text"] == "Test transcription"
        assert result["duration"] is None

    @patch("app.tools.extraction.audio_extractor.settings")
    @patch("app.tools.extraction.audio_extractor.OpenAI")
    def test_handles_response_without_language(
        self,
        mock_openai_class,
        mock_settings,
    ):
        """Should handle response without language field."""
        from app.tools.extraction.audio_extractor import transcribe_audio
        
        mock_settings.openai_api_key = "test-key"
        mock_settings.whisper_model = "whisper-1"
        
        response = MagicMock()
        response.text = "Test transcription"
        response.duration = 2.0
        # No language attribute
        del response.language
        
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = response
        mock_openai_class.return_value = mock_client
        
        result = transcribe_audio(b"audio bytes")
        
        assert result["text"] == "Test transcription"
        assert result["language"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Spanish Expense Examples Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSpanishAudioExamples:
    """Tests with realistic Spanish audio transcription examples."""

    @pytest.mark.parametrize(
        "transcription,expected_category,expected_method",
        [
            ("Pagué treinta soles por un taxi al aeropuerto", "transport", "cash"),
            ("Gasté cincuenta dólares en el supermercado con tarjeta", "in_house_food", "card"),
            ("Reservé el hotel por cien dólares", "lodging", "card"),
            ("Compré unas medicinas en la farmacia", "healthcare", "cash"),
            ("Pedí pizza por Rappi quince soles", "delivery", "card"),
        ],
    )
    @patch("app.tools.extraction.audio_extractor.transcribe_audio")
    @patch("app.tools.extraction.audio_extractor.extract_expense_from_text")
    def test_spanish_expense_examples(
        self,
        mock_extract_text,
        mock_transcribe,
        transcription,
        expected_category,
        expected_method,
    ):
        """Should correctly extract from realistic Spanish transcriptions."""
        from app.tools.extraction.audio_extractor import extract_expense_from_audio
        
        mock_transcribe.return_value = {
            "text": transcription,
            "language": "es",
            "duration": 5.0,
        }
        
        mock_expense = ExtractedExpense(
            amount=Decimal("50"),
            currency="USD",
            description=transcription[:50],
            category_candidate=expected_category,
            method=expected_method,
            merchant=None,
            card_hint=None,
            occurred_at=None,
            notes=None,
            installments=1,
            category_confidence=0.9,
            category_source="llm",
            confidence=0.85,
            raw_input=transcription,
        )
        mock_extract_text.return_value = mock_expense
        
        result = extract_expense_from_audio("test_audio.ogg")
        
        assert result.category_candidate == expected_category
        assert result.method == expected_method
