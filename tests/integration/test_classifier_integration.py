"""
Integration tests for the expense classifier.

These tests verify end-to-end classification behavior with
real (or mocked) model inference. Some tests are marked
as slow and should be skipped in CI.

Run with: pytest tests/integration/test_classifier_integration.py -v
Skip slow tests: pytest -m "not slow"
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.expense_classifier import (
    ClassificationResult,
    HuggingFaceClassifier,
    classify_expense_with_fallback,
)


class TestSpanishDescriptionClassification:
    """Test classification of Spanish expense descriptions."""

    @pytest.fixture
    def mock_classifier_pipeline(self):
        """Mock the HuggingFace pipeline for testing."""
        mock = MagicMock()
        # Default response simulating Spanish category classification
        mock.return_value = {
            "labels": [
                "Transporte taxi uber bus metro",
                "Otros gastos misceláneos",
                "Comida para llevar o delivery",
                "Comer en restaurante o fuera de casa",
                "Compras de supermercado para cocinar en casa",
            ],
            "scores": [0.75, 0.10, 0.08, 0.05, 0.02],
        }
        return mock

    @pytest.mark.asyncio
    async def test_classify_taxi_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of taxi expense in Spanish."""
        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Taxi al aeropuerto El Dorado",
            merchant="Uber"
        )

        assert result.category_slug == "transport"
        assert result.confidence >= 0.5
        assert result.source in ("zero_shot", "ml_classifier")

    @pytest.mark.asyncio
    async def test_classify_restaurant_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of restaurant expense in Spanish."""
        # Update mock for restaurant scenario
        mock_classifier_pipeline.return_value = {
            "labels": [
                "Comer en restaurante o fuera de casa",
                "Comida para llevar o delivery",
                "Otros gastos misceláneos",
            ],
            "scores": [0.85, 0.10, 0.05],
        }

        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Almuerzo con el equipo",
            merchant="Restaurante La Puerta"
        )

        assert result.category_slug == "out_house_food"
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_classify_supermarket_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of supermarket expense in Spanish."""
        mock_classifier_pipeline.return_value = {
            "labels": [
                "Compras de supermercado para cocinar en casa",
                "Otros gastos misceláneos",
            ],
            "scores": [0.90, 0.10],
        }

        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Compra de víveres semanales",
            merchant="Éxito"
        )

        assert result.category_slug == "in_house_food"
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_classify_delivery_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of delivery expense in Spanish."""
        mock_classifier_pipeline.return_value = {
            "labels": [
                "Comida para llevar o delivery",
                "Comer en restaurante o fuera de casa",
                "Otros gastos misceláneos",
            ],
            "scores": [0.88, 0.08, 0.04],
        }

        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Hamburguesa domicilio",
            merchant="Rappi"
        )

        assert result.category_slug == "delivery"
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_classify_hotel_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of hotel expense in Spanish."""
        mock_classifier_pipeline.return_value = {
            "labels": [
                "Alojamiento u hospedaje",
                "Turismo entretenimiento actividades",
            ],
            "scores": [0.92, 0.08],
        }

        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Dos noches de hospedaje",
            merchant="Hotel Marriott"
        )

        assert result.category_slug == "lodging"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_classify_pharmacy_expense_spanish(self, mock_classifier_pipeline):
        """Test classification of pharmacy expense in Spanish."""
        mock_classifier_pipeline.return_value = {
            "labels": [
                "Salud médico farmacia",
                "Otros gastos misceláneos",
            ],
            "scores": [0.87, 0.13],
        }

        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = mock_classifier_pipeline
        classifier._loaded = True

        result = await classifier.classify(
            description="Medicamentos para el dolor de cabeza",
            merchant="Droguería La Rebaja"
        )

        assert result.category_slug == "healthcare"
        assert result.confidence >= 0.8


class TestFallbackBehavior:
    """Test fallback behavior when classifier fails or is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_to_misc_on_error(self):
        """Should return misc category on classification error."""
        classifier = HuggingFaceClassifier(model_name="nonexistent-model")
        classifier._loaded = True
        classifier._classifier = MagicMock(side_effect=Exception("Model error"))

        result = await classifier.classify("gasto desconocido")

        assert result.category_slug == "misc"
        assert result.confidence == 0.0
        assert result.source == "error_fallback"

    @pytest.mark.asyncio
    async def test_classify_with_fallback_uses_high_llm_confidence(self):
        """Should use LLM category when confidence is high."""
        with patch("app.services.expense_classifier.settings") as mock_settings:
            mock_settings.confidence_threshold = 0.7

            result = await classify_expense_with_fallback(
                description="taxi al centro",
                llm_category="transport",
                llm_confidence=0.95,
            )

            assert result.category_slug == "transport"
            assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_classify_with_fallback_tries_ml_on_low_confidence(self):
        """Should try ML classifier when LLM confidence is low."""
        mock_classifier = MagicMock()
        mock_classifier.is_available.return_value = True
        mock_classifier.classify = AsyncMock(
            return_value=ClassificationResult(
                category_slug="transport",
                confidence=0.85,
                source="zero_shot",
            )
        )

        with (
            patch("app.services.expense_classifier.settings") as mock_settings,
            patch(
                "app.services.expense_classifier.get_expense_classifier",
                return_value=mock_classifier,
            ),
        ):
            mock_settings.confidence_threshold = 0.7

            result = await classify_expense_with_fallback(
                description="uber",
                llm_category="misc",
                llm_confidence=0.4,
            )

            # ML should be called and result used
            mock_classifier.classify.assert_called_once()
            assert result.confidence == 0.85


class TestModelAvailability:
    """Test classifier availability checks."""

    def test_classifier_unavailable_before_load(self):
        """Classifier should report unavailable before loading."""
        # Don't let it actually load the model
        with patch(
            "app.services.expense_classifier.HuggingFaceClassifier._load_model",
            side_effect=Exception("Model not found")
        ):
            classifier = HuggingFaceClassifier(model_name="nonexistent")
            assert classifier.is_available() is False

    def test_classifier_available_after_mock_load(self):
        """Classifier should report available after successful load."""
        classifier = HuggingFaceClassifier(model_name="test-model")
        classifier._classifier = MagicMock()
        classifier._loaded = True

        assert classifier.is_available() is True


@pytest.mark.slow
class TestRealModelClassification:
    """
    Tests with real HuggingFace models.
    
    These tests are marked as slow and require downloading models.
    Skip in CI with: pytest -m "not slow"
    """

    @pytest.mark.skip(reason="Requires downloading large model")
    @pytest.mark.asyncio
    async def test_real_model_classification(self):
        """Test with real facebook/bart-large-mnli model."""
        classifier = HuggingFaceClassifier(
            model_name="facebook/bart-large-mnli"
        )

        result = await classifier.classify(
            description="Taxi al aeropuerto",
            merchant="Uber"
        )

        assert result.category_slug in [
            "transport",
            "tourism",
            "misc",
        ]
        assert 0 <= result.confidence <= 1

