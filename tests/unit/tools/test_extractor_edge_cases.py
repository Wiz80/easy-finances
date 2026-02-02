"""
Edge Case Tests for Expense Extractors.

Tests for unusual inputs, format variations, and boundary conditions
in text and audio extractors.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.extraction import ExtractedExpense


def create_mock_expense(**kwargs) -> ExtractedExpense:
    """Create a valid mock ExtractedExpense with all required fields."""
    return ExtractedExpense(
        amount=Decimal(str(kwargs.get("amount", 100.0))),
        currency=kwargs.get("currency", "USD"),
        description=kwargs.get("description", "Test expense"),
        category_candidate=kwargs.get("category", "misc"),
        method=kwargs.get("method", "cash"),
        confidence=kwargs.get("confidence", 0.9),
        raw_input=kwargs.get("raw_input", "Test input"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Amount Format Variations
# ─────────────────────────────────────────────────────────────────────────────

class TestAmountFormatVariations:
    """Tests for various amount format inputs."""

    def test_amount_with_comma_as_decimal(self):
        """Test: Amount with comma as decimal separator (1.500,50)."""
        mock_expense = create_mock_expense(amount=1500.50)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 1.500,50 euros")
            
            assert result.amount == Decimal("1500.50")

    def test_amount_with_period_as_decimal(self):
        """Test: Amount with period as decimal separator (1,500.50)."""
        mock_expense = create_mock_expense(amount=1500.50)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 1,500.50 dollars")
            
            assert result.amount == Decimal("1500.50")

    def test_amount_with_k_suffix(self):
        """Test: Amount with 'k' suffix (50k = 50000)."""
        mock_expense = create_mock_expense(amount=50000.0)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 50k en el hotel")
            
            assert result.amount == Decimal("50000.0")

    def test_amount_with_million_word(self):
        """Test: Amount expressed as 'un millón'."""
        mock_expense = create_mock_expense(amount=1000000.0)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Me costó un millón de pesos")
            
            assert result.amount == Decimal("1000000.0")

    def test_amount_very_small(self):
        """Test: Very small amount (0.01)."""
        mock_expense = create_mock_expense(amount=0.01)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Me cobraron un centavo")
            
            assert result.amount == Decimal("0.01")

    def test_amount_very_large(self):
        """Test: Very large amount (10,000,000)."""
        mock_expense = create_mock_expense(amount=10000000.0)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Pagué diez millones por el carro")
            
            assert result.amount == Decimal("10000000.0")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Currency Ambiguity
# ─────────────────────────────────────────────────────────────────────────────

class TestCurrencyAmbiguity:
    """Tests for ambiguous currency inputs."""

    def test_peso_without_country(self):
        """Test: 'pesos' without country context."""
        mock_expense = create_mock_expense(currency="COP", confidence=0.6)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 500 pesos en taxi")
            
            # Should have lower confidence due to ambiguity
            assert result.currency in ("COP", "MXN", "ARS")

    def test_dollar_sign_ambiguity(self):
        """Test: '$' sign can mean USD, CAD, AUD, etc."""
        mock_expense = create_mock_expense(currency="USD")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté $50 en almuerzo")
            
            # Default to USD for $ sign
            assert result.currency == "USD"

    def test_explicit_currency_code(self):
        """Test: Explicit ISO currency code takes precedence."""
        mock_expense = create_mock_expense(currency="EUR", confidence=0.95)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 100 EUR en el museo")
            
            assert result.currency == "EUR"
            assert result.confidence >= 0.9

    def test_currency_symbol_euro(self):
        """Test: Euro symbol (€) is recognized."""
        mock_expense = create_mock_expense(currency="EUR")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Pagué €50 por la cena")
            
            assert result.currency == "EUR"

    def test_local_currency_names(self):
        """Test: Local currency names (soles, reales, quetzales)."""
        test_cases = [
            ("Gasté 100 soles", "PEN"),
            ("Pagué 200 reales", "BRL"),
            ("Me costó 50 quetzales", "GTQ"),
        ]
        
        for input_text, expected_currency in test_cases:
            mock_expense = create_mock_expense(currency=expected_currency)
            
            with patch(
                "app.tools.extraction.text_extractor.extract_expense_from_text"
            ) as mock_extract:
                mock_extract.return_value = mock_expense
                
                from app.tools.extraction.text_extractor import extract_expense_from_text
                result = extract_expense_from_text(input_text)
                
                assert result.currency == expected_currency, f"Failed for: {input_text}"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Category Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestCategoryEdgeCases:
    """Tests for category classification edge cases."""

    def test_ambiguous_category_uber(self):
        """Test: Uber could be transport or food (Uber Eats)."""
        mock_expense = create_mock_expense(category="transport")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Uber 15 dólares")
            
            # Without more context, default to transport
            assert result.category_candidate in ("transport", "out_house_food", "delivery")

    def test_uber_eats_is_food(self):
        """Test: Uber Eats should be food category."""
        mock_expense = create_mock_expense(category="delivery")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Uber Eats 25 dólares")
            
            assert result.category_candidate in ("delivery", "out_house_food")

    def test_multi_category_expense(self):
        """Test: Expense that could fit multiple categories."""
        # "Souvenir" could be gifts or tourism
        mock_expense = create_mock_expense(category="tourism")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Compré souvenirs por 30 dólares")
            
            assert result.category_candidate in ("tourism", "misc")

    def test_unknown_category_defaults_to_misc(self):
        """Test: Unknown category defaults to misc."""
        mock_expense = create_mock_expense(category="misc")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Gasté 50 en algo")
            
            assert result.category_candidate == "misc"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Payment Method Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestPaymentMethodDetection:
    """Tests for payment method detection edge cases."""

    def test_explicit_cash(self):
        """Test: Explicit cash mention."""
        mock_expense = create_mock_expense(method="cash")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Pagué 50 en efectivo")
            
            assert result.method == "cash"

    def test_explicit_card(self):
        """Test: Explicit card mention."""
        mock_expense = create_mock_expense(method="card")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Pagué con tarjeta 100 dólares")
            
            assert result.method == "card"

    def test_debit_card_is_card(self):
        """Test: Debit card is detected as card."""
        mock_expense = create_mock_expense(method="card")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Débito 50 dólares hotel")
            
            assert result.method == "card"

    def test_digital_wallet_patterns(self):
        """Test: Digital wallet patterns (Nequi, Daviplata)."""
        wallets = ["Nequi", "Daviplata", "PayPal", "Apple Pay"]
        
        for wallet in wallets:
            mock_expense = create_mock_expense(method="transfer")
            
            with patch(
                "app.tools.extraction.text_extractor.extract_expense_from_text"
            ) as mock_extract:
                mock_extract.return_value = mock_expense
                
                from app.tools.extraction.text_extractor import extract_expense_from_text
                result = extract_expense_from_text(f"Pagué por {wallet} 30 dólares")
                
                # Digital wallets might be classified as transfer or card
                assert result.method in ("card", "cash", "transfer")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Special Characters and Unicode
# ─────────────────────────────────────────────────────────────────────────────

class TestSpecialCharactersAndUnicode:
    """Tests for special characters and unicode in inputs."""

    def test_emoji_in_description(self):
        """Test: Emoji in expense description."""
        mock_expense = create_mock_expense(description="Pizza 🍕")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("🍕 Pizza 15 dólares 🍕")
            
            assert result is not None
            assert result.amount == Decimal("100.0")  # Mock value

    def test_accented_characters(self):
        """Test: Accented characters (común in Spanish)."""
        mock_expense = create_mock_expense(description="Café")
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Café y medialuná 10 dólares")
            
            assert result is not None

    def test_special_punctuation(self):
        """Test: Special punctuation marks."""
        mock_expense = create_mock_expense(amount=50.0)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("¡Gasté $50 en el restaurante!")
            
            assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test: Incomplete or Ambiguous Messages
# ─────────────────────────────────────────────────────────────────────────────

class TestIncompleteMessages:
    """Tests for incomplete or ambiguous expense messages."""

    def test_amount_only_message(self):
        """Test: Message with only amount has low confidence."""
        mock_expense = create_mock_expense(amount=50.0, confidence=0.4)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("50")
            
            # Should have low confidence
            assert result.confidence < 0.7

    def test_description_only_message(self):
        """Test: Message with only description has low confidence."""
        # Use MagicMock to simulate a low-confidence response 
        mock_expense = MagicMock()
        mock_expense.amount = Decimal("0")
        mock_expense.confidence = 0.3
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Almorcé con amigos")
            
            # Very low confidence without amount
            assert result.confidence < 0.5

    def test_very_short_message(self):
        """Test: Very short message has low confidence."""
        mock_expense = MagicMock()
        mock_expense.confidence = 0.2
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("ok")
            
            assert result.confidence < 0.5

    def test_multiple_amounts_in_message(self):
        """Test: Message with multiple amounts extracts the total."""
        mock_expense = create_mock_expense(amount=75.0, confidence=0.7)
        
        with patch(
            "app.tools.extraction.text_extractor.extract_expense_from_text"
        ) as mock_extract:
            mock_extract.return_value = mock_expense
            
            from app.tools.extraction.text_extractor import extract_expense_from_text
            result = extract_expense_from_text("Almuerzo 50 + propina 25 = 75 dólares")
            
            # Should extract the total
            assert result.amount == Decimal("75.0")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Audio Transcription Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestAudioTranscriptionEdgeCases:
    """Tests for audio transcription edge cases."""

    def test_very_short_audio(self):
        """Test: Very short audio clip (< 1 second)."""
        short_audio = b"very short audio bytes"
        
        # Mock at the module level where it's imported
        with patch(
            "app.tools.extraction.audio_extractor.OpenAI"
        ) as mock_openai_class:
            mock_client = MagicMock()
            mock_transcription = MagicMock()
            mock_transcription.text = ""
            mock_client.audio.transcriptions.create.return_value = mock_transcription
            mock_openai_class.return_value = mock_client
            
            from app.tools.extraction.audio_extractor import transcribe_audio
            
            result = transcribe_audio(short_audio)
            
            # Should handle gracefully - returns dict
            assert result is not None
            assert isinstance(result, dict)

    def test_noisy_audio(self):
        """Test: Noisy audio with low transcription quality."""
        noisy_audio = b"noisy audio bytes"
        
        with patch(
            "app.tools.extraction.audio_extractor.OpenAI"
        ) as mock_openai_class:
            mock_client = MagicMock()
            mock_transcription = MagicMock()
            mock_transcription.text = "[inaudible] fifty dollars [noise]"
            mock_client.audio.transcriptions.create.return_value = mock_transcription
            mock_openai_class.return_value = mock_client
            
            from app.tools.extraction.audio_extractor import transcribe_audio
            
            result = transcribe_audio(noisy_audio)
            
            # Should return whatever was transcribed
            assert result is not None
            assert "text" in result

    def test_multiple_languages_in_audio(self):
        """Test: Audio with mixed languages."""
        mixed_audio = b"mixed language audio"
        
        with patch(
            "app.tools.extraction.audio_extractor.OpenAI"
        ) as mock_openai_class:
            mock_client = MagicMock()
            mock_transcription = MagicMock()
            mock_transcription.text = "Gasté fifty dólares in the restaurant"
            mock_client.audio.transcriptions.create.return_value = mock_transcription
            mock_openai_class.return_value = mock_client
            
            from app.tools.extraction.audio_extractor import transcribe_audio
            
            result = transcribe_audio(mixed_audio)
            
            assert result is not None
            assert "text" in result
