"""
Unit tests for IE Agent extractor nodes.

Tests:
- Text extraction node
- Audio extraction node
- Image extraction node
- Error handling in each node
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.ie_agent.nodes.extractors import (
    extract_text_node,
    extract_audio_node,
    extract_image_node,
    error_node,
    _receipt_to_expense,
)
from app.agents.ie_agent.state import IEAgentState
from app.schemas.extraction import ExtractedExpense, ExtractedReceipt


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def base_state() -> IEAgentState:
    """Create a base state with required fields."""
    return {
        "request_id": "test-123",
        "user_id": uuid4(),
        "account_id": uuid4(),
        "errors": [],
    }


@pytest.fixture
def text_state(base_state) -> IEAgentState:
    """Create a state for text extraction."""
    return {
        **base_state,
        "raw_input": "Gasté 50000 pesos en almuerzo",
        "input_type": "text",
    }


@pytest.fixture
def audio_state(base_state) -> IEAgentState:
    """Create a state for audio extraction."""
    return {
        **base_state,
        "raw_input": b"\x00\x01\x02\x03",  # Mock audio bytes
        "input_type": "audio",
        "language": "es",
    }


@pytest.fixture
def image_state(base_state) -> IEAgentState:
    """Create a state for image extraction."""
    return {
        **base_state,
        "raw_input": b"\xff\xd8\xff\xe0",  # Mock JPEG bytes
        "input_type": "image",
        "filename": "receipt.jpg",
        "file_type": "image/jpeg",
    }


@pytest.fixture
def mock_extracted_expense():
    """Create a mock ExtractedExpense."""
    return ExtractedExpense(
        amount=Decimal("50000"),
        currency="COP",
        description="almuerzo",
        category_candidate="out_house_food",
        method="cash",
        merchant=None,
        card_hint=None,
        occurred_at=None,
        notes=None,
        installments=1,
        category_confidence=0.9,
        category_source="llm",
        confidence=0.85,
        raw_input="Gasté 50000 pesos en almuerzo",
    )


@pytest.fixture
def mock_extracted_receipt():
    """Create a mock ExtractedReceipt."""
    return ExtractedReceipt(
        merchant="SuperMercado El Ahorro",
        total_amount=Decimal("150.50"),
        currency="USD",
        occurred_at=None,
        line_items=[],
        tax_amount=None,
        tip_amount=None,
        payment_method="Visa ****1234",
        receipt_number="REC-001",
        category_candidate="in_house_food",
        confidence=0.88,
        raw_text="Receipt text...",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Text Extraction Node Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTextNode:
    """Tests for extract_text_node function."""

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_text")
    def test_successful_text_extraction(
        self, mock_extract, text_state, mock_extracted_expense
    ):
        """Should extract expense from text input."""
        mock_extract.return_value = mock_extracted_expense
        
        result = extract_text_node(text_state)
        
        assert result["extracted_expense"] == mock_extracted_expense
        assert result["confidence"] == 0.85
        assert result["status"] == "extracting"
        assert len(result["errors"]) == 0

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_text")
    def test_text_extraction_calls_extractor(self, mock_extract, text_state):
        """Should call extract_expense_from_text with correct args."""
        mock_extract.return_value = MagicMock(confidence=0.9)
        
        extract_text_node(text_state)
        
        mock_extract.assert_called_once()
        call_kwargs = mock_extract.call_args.kwargs
        assert call_kwargs["text"] == text_state["raw_input"]
        assert call_kwargs["request_id"] == text_state["request_id"]

    def test_non_string_input_raises_error(self, base_state):
        """Should return error for non-string input."""
        state = {
            **base_state,
            "raw_input": b"bytes instead of string",
            "input_type": "text",
        }
        
        result = extract_text_node(state)
        
        assert result["status"] == "error"
        assert any("string input" in e.lower() for e in result["errors"])

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_text")
    def test_extraction_failure_sets_error_status(self, mock_extract, text_state):
        """Should set error status when extraction fails."""
        mock_extract.side_effect = Exception("LLM API Error")
        
        result = extract_text_node(text_state)
        
        assert result["status"] == "error"
        assert result["error_node"] == "extract_text"
        assert any("Text extraction failed" in e for e in result["errors"])


# ─────────────────────────────────────────────────────────────────────────────
# Audio Extraction Node Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractAudioNode:
    """Tests for extract_audio_node function."""

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_audio")
    def test_successful_audio_extraction(
        self, mock_extract, audio_state, mock_extracted_expense
    ):
        """Should extract expense from audio input."""
        mock_extracted_expense.notes = "Transcription: Gasté cincuenta soles"
        mock_extract.return_value = mock_extracted_expense
        
        result = extract_audio_node(audio_state)
        
        assert result["extracted_expense"] == mock_extracted_expense
        assert result["status"] == "extracting"

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_audio")
    def test_audio_extraction_extracts_transcription(
        self, mock_extract, audio_state, mock_extracted_expense
    ):
        """Should extract transcription from notes."""
        mock_extracted_expense.notes = "Transcription: Gasté cincuenta soles en taxi"
        mock_extract.return_value = mock_extracted_expense
        
        result = extract_audio_node(audio_state)
        
        assert result["transcription"] == "Gasté cincuenta soles en taxi"

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_audio")
    def test_audio_extraction_passes_language(self, mock_extract, audio_state):
        """Should pass language to audio extractor."""
        mock_extract.return_value = MagicMock(confidence=0.9, notes=None)
        
        extract_audio_node(audio_state)
        
        call_kwargs = mock_extract.call_args.kwargs
        assert call_kwargs["language"] == "es"

    def test_non_bytes_input_raises_error(self, base_state):
        """Should return error for non-bytes input."""
        state = {
            **base_state,
            "raw_input": "string instead of bytes",
            "input_type": "audio",
        }
        
        result = extract_audio_node(state)
        
        assert result["status"] == "error"
        assert any("bytes input" in e.lower() for e in result["errors"])

    @patch("app.agents.ie_agent.nodes.extractors.extract_expense_from_audio")
    def test_audio_extraction_failure_sets_error(self, mock_extract, audio_state):
        """Should set error status when extraction fails."""
        mock_extract.side_effect = Exception("Whisper API Error")
        
        result = extract_audio_node(audio_state)
        
        assert result["status"] == "error"
        assert result["error_node"] == "extract_audio"


# ─────────────────────────────────────────────────────────────────────────────
# Image Extraction Node Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractImageNode:
    """Tests for extract_image_node function."""

    @patch("app.agents.ie_agent.nodes.extractors.extract_receipt_from_file")
    def test_successful_image_extraction(
        self, mock_extract, image_state, mock_extracted_receipt
    ):
        """Should extract receipt from image input."""
        mock_extract.return_value = mock_extracted_receipt
        
        result = extract_image_node(image_state)
        
        assert result["extracted_receipt"] == mock_extracted_receipt
        assert result["extracted_expense"] is not None
        assert result["status"] == "extracting"

    @patch("app.agents.ie_agent.nodes.extractors.extract_receipt_from_file")
    def test_image_creates_expense_from_receipt(
        self, mock_extract, image_state, mock_extracted_receipt
    ):
        """Should create ExtractedExpense from receipt data."""
        mock_extract.return_value = mock_extracted_receipt
        
        result = extract_image_node(image_state)
        
        expense = result["extracted_expense"]
        assert expense.amount == mock_extracted_receipt.total_amount
        assert expense.currency == mock_extracted_receipt.currency
        assert expense.merchant == mock_extracted_receipt.merchant

    @patch("app.agents.ie_agent.nodes.extractors.extract_receipt_from_file")
    def test_image_extraction_passes_filename(self, mock_extract, image_state):
        """Should pass filename to receipt extractor."""
        mock_extract.return_value = MagicMock(
            total_amount=Decimal("100"),
            currency="USD",
            merchant="Store",
            category_candidate="misc",
            confidence=0.9,
            payment_method=None,
            transaction_type=None,
            raw_markdown=None,
            raw_text="text",
            receipt_number=None,
            occurred_at=None,
        )
        
        extract_image_node(image_state)
        
        call_kwargs = mock_extract.call_args.kwargs
        assert call_kwargs["filename"] == "receipt.jpg"

    def test_non_bytes_input_raises_error(self, base_state):
        """Should return error for non-bytes input."""
        state = {
            **base_state,
            "raw_input": "string instead of bytes",
            "input_type": "image",
        }
        
        result = extract_image_node(state)
        
        assert result["status"] == "error"
        assert any("bytes input" in e.lower() for e in result["errors"])

    @patch("app.agents.ie_agent.nodes.extractors.extract_receipt_from_file")
    def test_image_extraction_failure_sets_error(self, mock_extract, image_state):
        """Should set error status when extraction fails."""
        mock_extract.side_effect = Exception("OCR Error")
        
        result = extract_image_node(image_state)
        
        assert result["status"] == "error"
        assert result["error_node"] == "extract_image"


# ─────────────────────────────────────────────────────────────────────────────
# Receipt to Expense Conversion Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestReceiptToExpense:
    """Tests for _receipt_to_expense helper function."""

    def test_basic_conversion(self, mock_extracted_receipt, base_state):
        """Should convert receipt to expense with correct fields."""
        result = _receipt_to_expense(mock_extracted_receipt, base_state)
        
        assert result.amount == mock_extracted_receipt.total_amount
        assert result.currency == mock_extracted_receipt.currency
        assert result.merchant == mock_extracted_receipt.merchant

    def test_detects_card_payment(self, base_state):
        """Should detect card payment from payment_method."""
        receipt = ExtractedReceipt(
            merchant="Store",
            total_amount=Decimal("100"),
            currency="USD",
            payment_method="Visa ****1234",
            category_candidate="misc",
            confidence=0.9,
        )
        
        result = _receipt_to_expense(receipt, base_state)
        
        assert result.method == "card"
        assert result.card_hint == "Visa"

    def test_defaults_to_cash_payment(self, base_state):
        """Should default to cash when payment method not specified."""
        receipt = ExtractedReceipt(
            merchant="Store",
            total_amount=Decimal("100"),
            currency="USD",
            payment_method=None,
            category_candidate="misc",
            confidence=0.9,
        )
        
        result = _receipt_to_expense(receipt, base_state)
        
        assert result.method == "cash"

    def test_includes_receipt_number_in_notes(self, base_state):
        """Should include receipt number in notes."""
        receipt = ExtractedReceipt(
            merchant="Store",
            total_amount=Decimal("100"),
            currency="USD",
            receipt_number="REC-12345",
            category_candidate="misc",
            confidence=0.9,
        )
        
        result = _receipt_to_expense(receipt, base_state)
        
        assert "REC-12345" in result.notes

    def test_includes_transaction_type_in_description(self, base_state):
        """Should include transaction type in description."""
        receipt = ExtractedReceipt(
            merchant="Bancolombia",
            total_amount=Decimal("500"),
            currency="COP",
            transaction_type="Transfer",
            category_candidate="misc",
            confidence=0.9,
        )
        
        result = _receipt_to_expense(receipt, base_state)
        
        assert "Transfer" in result.description

    def test_truncates_long_raw_input(self, base_state):
        """Should truncate raw_input to 2000 chars."""
        long_text = "A" * 3000
        receipt = ExtractedReceipt(
            merchant="Store",
            total_amount=Decimal("100"),
            currency="USD",
            raw_markdown=long_text,
            category_candidate="misc",
            confidence=0.9,
        )
        
        result = _receipt_to_expense(receipt, base_state)
        
        assert len(result.raw_input) == 2000


# ─────────────────────────────────────────────────────────────────────────────
# Error Node Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorNode:
    """Tests for error_node function."""

    def test_sets_error_status(self, base_state):
        """Should set status to error."""
        state = {
            **base_state,
            "input_type": "unknown",
        }
        
        result = error_node(state)
        
        assert result["status"] == "error"

    def test_adds_error_message(self, base_state):
        """Should add error message to errors list."""
        state = {
            **base_state,
            "input_type": "unknown",
            "errors": [],
        }
        
        result = error_node(state)
        
        assert len(result["errors"]) > 0
        assert "unknown" in result["errors"][0].lower()

    def test_sets_error_node_to_router(self, base_state):
        """Should set error_node to 'router'."""
        state = {
            **base_state,
            "input_type": "unknown",
        }
        
        result = error_node(state)
        
        assert result["error_node"] == "router"

    def test_preserves_existing_errors(self, base_state):
        """Should preserve existing errors."""
        state = {
            **base_state,
            "input_type": "unknown",
            "errors": ["Previous error"],
        }
        
        result = error_node(state)
        
        assert "Previous error" in result["errors"]
        assert len(result["errors"]) == 2
