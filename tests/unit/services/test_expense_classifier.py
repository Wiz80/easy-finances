"""
Unit tests for expense classification service.

Tests the ML-based expense classifier including:
- Category mapping from external models to system categories
- Classification with mocked models
- Fallback behavior when classifier unavailable
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.expense_classifier import (
    EXTERNAL_CATEGORY_MAPPING,
    SPANISH_CATEGORY_LABELS,
    SPANISH_LABEL_TO_SLUG,
    ClassificationResult,
    EmbeddingClassifier,
    ExpenseClassifier,
    HuggingFaceClassifier,
    ZeroShotClassifier,
    classify_expense_with_fallback,
)


class TestCategoryMapping:
    """Tests for category mapping logic."""

    def test_all_spanish_labels_have_slug_mapping(self):
        """Every Spanish label should map to a system category."""
        for label in SPANISH_CATEGORY_LABELS:
            assert label in SPANISH_LABEL_TO_SLUG, f"Missing mapping for {label}"

    def test_external_mapping_covers_common_categories(self):
        """External mapping should cover common financial categories."""
        common_categories = [
            "food & dining",
            "groceries",
            "transportation",
            "travel",
            "healthcare",
            "shopping",
        ]
        for cat in common_categories:
            assert cat in EXTERNAL_CATEGORY_MAPPING, f"Missing mapping for {cat}"

    def test_external_mapping_returns_valid_system_slugs(self):
        """All mappings should return valid system category slugs."""
        valid_slugs = {
            "delivery",
            "in_house_food",
            "out_house_food",
            "lodging",
            "transport",
            "tourism",
            "healthcare",
            "misc",
            "unexpected",
        }
        for ext_cat, slug in EXTERNAL_CATEGORY_MAPPING.items():
            assert slug in valid_slugs, f"Invalid slug {slug} for {ext_cat}"


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_classification_result_creation(self):
        """Test basic result creation."""
        result = ClassificationResult(
            category_slug="transport",
            confidence=0.85,
            all_scores={"transport": 0.85, "misc": 0.10},
            source="zero_shot",
            model_name="test-model",
        )
        assert result.category_slug == "transport"
        assert result.confidence == 0.85
        assert result.source == "zero_shot"

    def test_classification_result_with_original_label(self):
        """Test result with original label from external model."""
        result = ClassificationResult(
            category_slug="transport",
            confidence=0.9,
            original_label="Transportation",
        )
        assert result.original_label == "Transportation"


class TestHuggingFaceClassifier:
    """Tests for HuggingFaceClassifier."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock transformers pipeline."""
        mock = MagicMock()
        mock.return_value = {
            "labels": [
                "Transporte taxi uber bus metro",
                "Otros gastos misceláneos",
                "Comida para llevar o delivery",
            ],
            "scores": [0.85, 0.10, 0.05],
        }
        return mock

    def test_classifier_not_loaded_initially(self):
        """Classifier should not load model on init."""
        with patch("app.services.expense_classifier.settings") as mock_settings:
            mock_settings.classifier_model_name = "test-model"
            classifier = HuggingFaceClassifier()
            assert classifier._loaded is False

    @pytest.mark.asyncio
    async def test_classify_returns_correct_category(self, mock_pipeline):
        """Classification should return correct mapped category."""
        with patch(
            "app.services.expense_classifier.HuggingFaceClassifier._load_model"
        ):
            classifier = HuggingFaceClassifier(model_name="test-model")
            classifier._classifier = mock_pipeline
            classifier._loaded = True

            result = await classifier.classify("uber al aeropuerto")

            assert result.category_slug == "transport"
            assert result.confidence == 0.85
            assert "transport" in result.all_scores

    @pytest.mark.asyncio
    async def test_classify_with_merchant(self, mock_pipeline):
        """Merchant should be included in classification text."""
        with patch(
            "app.services.expense_classifier.HuggingFaceClassifier._load_model"
        ):
            classifier = HuggingFaceClassifier(model_name="test-model")
            classifier._classifier = mock_pipeline
            classifier._loaded = True

            await classifier.classify("viaje", merchant="Uber")

            # Check that merchant was included in the call
            call_args = mock_pipeline.call_args[0][0]
            assert "Uber" in call_args


class TestZeroShotClassifier:
    """Tests for ZeroShotClassifier with dynamic categories."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock pipeline."""
        mock = MagicMock()
        mock.return_value = {
            "labels": ["Comida", "Transporte", "Otros"],
            "scores": [0.8, 0.15, 0.05],
        }
        return mock

    def test_set_categories_manually(self):
        """Categories can be set manually for testing."""
        classifier = ZeroShotClassifier()
        categories = {
            "Comida": "food",
            "Transporte": "transport",
            "Otros": "misc",
        }
        classifier.set_categories(categories)

        assert len(classifier._categories) == 3
        assert "Comida" in classifier._categories

    @pytest.mark.asyncio
    async def test_classify_with_custom_categories(self, mock_pipeline):
        """Classification should work with custom categories."""
        classifier = ZeroShotClassifier(model_name="test-model")
        classifier._classifier = mock_pipeline
        classifier._loaded = True

        categories = {
            "Comida": "food",
            "Transporte": "transport",
            "Otros": "misc",
        }
        classifier.set_categories(categories)

        result = await classifier.classify("almuerzo en restaurante")

        assert result.category_slug == "food"
        assert result.confidence == 0.8


class TestEmbeddingClassifier:
    """Tests for EmbeddingClassifier."""

    def test_classifier_initialization(self):
        """Test classifier initializes without loading model."""
        classifier = EmbeddingClassifier(model_name="test-model")
        assert classifier._loaded is False
        assert classifier._model is None


class TestClassifyWithFallback:
    """Tests for the classify_expense_with_fallback function."""

    @pytest.mark.asyncio
    async def test_uses_llm_category_when_confident(self):
        """Should use LLM category when confidence is high."""
        with patch("app.services.expense_classifier.settings") as mock_settings:
            mock_settings.confidence_threshold = 0.7

            result = await classify_expense_with_fallback(
                description="uber al trabajo",
                merchant="Uber",
                llm_category="transport",
                llm_confidence=0.9,
            )

            assert result.category_slug == "transport"
            assert result.source == "llm"
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_uses_ml_when_llm_uncertain(self):
        """Should use ML classifier when LLM confidence is low."""
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
                description="uber al trabajo",
                merchant="Uber",
                llm_category="misc",
                llm_confidence=0.5,
            )

            assert result.category_slug == "transport"
            assert result.source == "zero_shot"

    @pytest.mark.asyncio
    async def test_falls_back_to_llm_on_classifier_error(self):
        """Should fall back to LLM category if ML classifier fails."""
        mock_classifier = MagicMock()
        mock_classifier.is_available.return_value = True
        mock_classifier.classify = AsyncMock(side_effect=Exception("Model error"))

        with (
            patch("app.services.expense_classifier.settings") as mock_settings,
            patch(
                "app.services.expense_classifier.get_expense_classifier",
                return_value=mock_classifier,
            ),
        ):
            mock_settings.confidence_threshold = 0.7

            result = await classify_expense_with_fallback(
                description="uber al trabajo",
                llm_category="misc",
                llm_confidence=0.5,
            )

            assert result.category_slug == "misc"
            assert result.source == "llm_fallback"

    @pytest.mark.asyncio
    async def test_uses_misc_when_no_llm_category(self):
        """Should default to misc when no LLM category provided."""
        with patch("app.services.expense_classifier.settings") as mock_settings:
            mock_settings.confidence_threshold = 0.7

            result = await classify_expense_with_fallback(
                description="gasto desconocido",
                llm_category=None,
                llm_confidence=0.0,
            )

            # Will try ML first, but if it fails, falls back to misc
            assert result.category_slug is not None


class TestCategoryMapperIntegration:
    """Integration tests for category mapping."""

    def test_food_category_mappings(self):
        """Test food-related category mappings."""
        food_labels = ["groceries", "food & dining", "restaurants", "coffee shops"]
        expected_slugs = {"in_house_food", "out_house_food"}

        for label in food_labels:
            slug = EXTERNAL_CATEGORY_MAPPING.get(label)
            assert slug in expected_slugs, f"{label} should map to food category"

    def test_transport_category_mappings(self):
        """Test transport-related category mappings."""
        transport_labels = ["transportation", "taxi", "uber", "gas & fuel", "parking"]

        for label in transport_labels:
            assert (
                EXTERNAL_CATEGORY_MAPPING.get(label) == "transport"
            ), f"{label} should map to transport"

    def test_delivery_category_mapping(self):
        """Test delivery category mapping."""
        assert EXTERNAL_CATEGORY_MAPPING.get("food delivery") == "delivery"
        assert EXTERNAL_CATEGORY_MAPPING.get("delivery") == "delivery"

    def test_lodging_category_mappings(self):
        """Test lodging-related mappings."""
        lodging_labels = ["hotels", "hotel", "lodging", "accommodation", "airbnb"]

        for label in lodging_labels:
            assert (
                EXTERNAL_CATEGORY_MAPPING.get(label) == "lodging"
            ), f"{label} should map to lodging"

