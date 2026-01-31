"""
Expense classification service using open source ML models.

Provides ML-based expense classification as a fallback when LLM confidence
is low. Supports multiple classification strategies:

1. HuggingFace pre-trained models (zero-shot or fine-tuned)
2. Sentence embeddings with similarity search

This module is designed to:
- Improve category accuracy for Spanish descriptions
- Reduce LLM calls for simple categorizations
- Enable fine-tuning with user correction data
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings
from app.logging_config import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Category Mapping
# ─────────────────────────────────────────────────────────────────────────────

# System categories from the MVP
SYSTEM_CATEGORIES = {
    "delivery": "Delivery",
    "in_house_food": "Comida en Casa",
    "out_house_food": "Comida Fuera",
    "lodging": "Alojamiento",
    "transport": "Transporte",
    "tourism": "Turismo",
    "healthcare": "Salud",
    "misc": "Otros",
    "unexpected": "Gastos Inesperados",
}

# Mapping from external model labels to system categories
# Keys are lowercase versions of common model output labels
EXTERNAL_CATEGORY_MAPPING: dict[str, str] = {
    # Food related
    "food & dining": "out_house_food",
    "food_and_dining": "out_house_food",
    "restaurants": "out_house_food",
    "dining": "out_house_food",
    "fast food": "out_house_food",
    "coffee shops": "out_house_food",
    "cafes": "out_house_food",
    "groceries": "in_house_food",
    "supermarket": "in_house_food",
    "grocery": "in_house_food",
    "food delivery": "delivery",
    "delivery": "delivery",
    # Transport
    "transportation": "transport",
    "transport": "transport",
    "gas & fuel": "transport",
    "gas": "transport",
    "fuel": "transport",
    "taxi": "transport",
    "uber": "transport",
    "rideshare": "transport",
    "public transit": "transport",
    "parking": "transport",
    "auto & transport": "transport",
    # Travel & Lodging
    "travel": "tourism",
    "hotels": "lodging",
    "hotel": "lodging",
    "lodging": "lodging",
    "accommodation": "lodging",
    "airbnb": "lodging",
    "vacation": "tourism",
    "flights": "transport",
    "airlines": "transport",
    # Entertainment
    "entertainment": "tourism",
    "movies": "tourism",
    "music": "tourism",
    "games": "tourism",
    "sports": "tourism",
    "recreation": "tourism",
    # Health
    "health & fitness": "healthcare",
    "health": "healthcare",
    "healthcare": "healthcare",
    "medical": "healthcare",
    "pharmacy": "healthcare",
    "doctor": "healthcare",
    "fitness": "healthcare",
    "gym": "healthcare",
    # Shopping & Other
    "shopping": "misc",
    "clothing": "misc",
    "electronics": "misc",
    "home": "misc",
    "utilities": "misc",
    "bills & utilities": "misc",
    "personal care": "misc",
    "education": "misc",
    "gifts & donations": "misc",
    "fees & charges": "misc",
    "transfer": "misc",
    "uncategorized": "misc",
    "other": "misc",
}

# Spanish category labels for zero-shot classification
SPANISH_CATEGORY_LABELS = [
    "Comida para llevar o delivery",
    "Compras de supermercado para cocinar en casa",
    "Comer en restaurante o fuera de casa",
    "Alojamiento u hospedaje",
    "Transporte taxi uber bus metro",
    "Turismo entretenimiento actividades",
    "Salud médico farmacia",
    "Otros gastos misceláneos",
]

# Mapping from Spanish labels to slugs
SPANISH_LABEL_TO_SLUG = {
    "Comida para llevar o delivery": "delivery",
    "Compras de supermercado para cocinar en casa": "in_house_food",
    "Comer en restaurante o fuera de casa": "out_house_food",
    "Alojamiento u hospedaje": "lodging",
    "Transporte taxi uber bus metro": "transport",
    "Turismo entretenimiento actividades": "tourism",
    "Salud médico farmacia": "healthcare",
    "Otros gastos misceláneos": "misc",
}


# ─────────────────────────────────────────────────────────────────────────────
# Result Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ClassificationResult:
    """Result of expense classification."""

    category_slug: str
    confidence: float
    all_scores: dict[str, float] = field(default_factory=dict)
    source: str = "ml_classifier"  # "ml_classifier", "zero_shot", "embeddings"
    model_name: str = ""
    original_label: str | None = None  # Original label from model before mapping


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base Classifier
# ─────────────────────────────────────────────────────────────────────────────


class ExpenseClassifier(ABC):
    """Abstract base class for expense classifiers."""

    @abstractmethod
    async def classify(
        self,
        description: str,
        merchant: str | None = None,
    ) -> ClassificationResult:
        """
        Classify an expense based on description and merchant.

        Args:
            description: Expense description text
            merchant: Optional merchant/vendor name

        Returns:
            ClassificationResult with category slug and confidence
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the classifier is available (model loaded)."""
        pass

    def _map_to_system_category(self, label: str) -> str:
        """Map external model label to system category slug."""
        label_lower = label.lower().strip()

        # Direct match in mapping
        if label_lower in EXTERNAL_CATEGORY_MAPPING:
            return EXTERNAL_CATEGORY_MAPPING[label_lower]

        # Partial match
        for key, slug in EXTERNAL_CATEGORY_MAPPING.items():
            if key in label_lower or label_lower in key:
                return slug

        # Default to misc
        return "misc"


# ─────────────────────────────────────────────────────────────────────────────
# HuggingFace Classifier (Pre-trained)
# ─────────────────────────────────────────────────────────────────────────────


class HuggingFaceClassifier(ExpenseClassifier):
    """
    Classifier using pre-trained HuggingFace text classification models.

    Default model: facebook/bart-large-mnli (zero-shot capable)
    Alternative: sentence-transformers for embedding-based classification
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str = "cpu",
    ):
        """
        Initialize the classifier.

        Args:
            model_name: HuggingFace model name (default from settings)
            device: Device to run on ("cpu", "cuda", "mps")
        """
        self.model_name = model_name or settings.classifier_model_name
        self.device = device
        self._classifier = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy load the model on first use."""
        if self._loaded:
            return

        try:
            from transformers import pipeline

            logger.info(
                "loading_classification_model",
                model_name=self.model_name,
                device=self.device,
            )

            self._classifier = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device if self.device != "cpu" else -1,
            )
            self._loaded = True

            logger.info("classification_model_loaded", model_name=self.model_name)

        except Exception as e:
            logger.error(
                "failed_to_load_classification_model",
                model_name=self.model_name,
                error=str(e),
            )
            self._loaded = False
            raise

    def is_available(self) -> bool:
        """Check if classifier is available."""
        if not self._loaded:
            try:
                self._load_model()
            except Exception:
                return False
        return self._classifier is not None

    async def classify(
        self,
        description: str,
        merchant: str | None = None,
    ) -> ClassificationResult:
        """
        Classify expense using zero-shot classification.

        Uses Spanish category labels for better accuracy with Spanish descriptions.
        """
        if not self.is_available():
            raise RuntimeError("Classifier not available")

        # Combine description and merchant for better context
        text = description.strip()
        if merchant:
            text = f"{merchant}: {text}"

        logger.debug(
            "classifying_expense",
            text_preview=text[:100],
            model=self.model_name,
        )

        try:
            result = self._classifier(
                text,
                candidate_labels=SPANISH_CATEGORY_LABELS,
                hypothesis_template="Este gasto es de la categoría: {}.",
                multi_label=False,
            )

            # Get top label and score
            top_label = result["labels"][0]
            top_score = result["scores"][0]

            # Map to system category
            category_slug = SPANISH_LABEL_TO_SLUG.get(top_label, "misc")

            # Build all scores dict
            all_scores = {}
            for label, score in zip(result["labels"], result["scores"]):
                slug = SPANISH_LABEL_TO_SLUG.get(label, "misc")
                if slug not in all_scores or score > all_scores[slug]:
                    all_scores[slug] = score

            logger.info(
                "expense_classified",
                category=category_slug,
                confidence=top_score,
                original_label=top_label,
                model=self.model_name,
            )

            return ClassificationResult(
                category_slug=category_slug,
                confidence=top_score,
                all_scores=all_scores,
                source="zero_shot",
                model_name=self.model_name,
                original_label=top_label,
            )

        except Exception as e:
            logger.error(
                "classification_failed",
                error=str(e),
                text_preview=text[:100],
            )
            # Return low-confidence misc on error
            return ClassificationResult(
                category_slug="misc",
                confidence=0.0,
                all_scores={"misc": 0.0},
                source="error_fallback",
                model_name=self.model_name,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Zero-Shot Classifier (More Flexible)
# ─────────────────────────────────────────────────────────────────────────────


class ZeroShotClassifier(ExpenseClassifier):
    """
    Zero-shot classifier that can work with dynamic category labels.

    Loads categories from database for maximum flexibility.
    Ideal for custom user categories in the future.
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self._classifier = None
        self._loaded = False
        self._categories: list[str] = []
        self._category_slug_map: dict[str, str] = {}

    def _load_model(self) -> None:
        """Lazy load the model."""
        if self._loaded:
            return

        try:
            from transformers import pipeline

            self._classifier = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device if self.device != "cpu" else -1,
            )
            self._loaded = True
        except Exception as e:
            logger.error("failed_to_load_zero_shot_model", error=str(e))
            raise

    async def load_categories_from_db(self, db: "AsyncSession") -> None:
        """
        Load active categories from database.

        Args:
            db: Async database session
        """
        from sqlalchemy import select

        from app.models.category import Category

        result = await db.execute(
            select(Category).where(Category.is_active == True)  # noqa: E712
        )
        categories = result.scalars().all()

        self._categories = [c.name for c in categories]
        self._category_slug_map = {c.name: c.slug for c in categories}

        logger.info(
            "categories_loaded_from_db",
            count=len(self._categories),
            categories=self._categories,
        )

    def set_categories(self, categories: dict[str, str]) -> None:
        """
        Set categories manually (for testing or static use).

        Args:
            categories: Dict mapping category name to slug
        """
        self._categories = list(categories.keys())
        self._category_slug_map = categories

    def is_available(self) -> bool:
        """Check if classifier is available."""
        if not self._loaded:
            try:
                self._load_model()
            except Exception:
                return False
        return self._classifier is not None and len(self._categories) > 0

    async def classify(
        self,
        description: str,
        merchant: str | None = None,
    ) -> ClassificationResult:
        """Classify using loaded categories."""
        if not self._loaded:
            self._load_model()

        if not self._categories:
            # Use default Spanish labels if no categories loaded
            self._categories = SPANISH_CATEGORY_LABELS
            self._category_slug_map = SPANISH_LABEL_TO_SLUG

        text = description.strip()
        if merchant:
            text = f"{merchant}: {text}"

        result = self._classifier(
            text,
            candidate_labels=self._categories,
            hypothesis_template="Este gasto es de la categoría {}.",
        )

        top_label = result["labels"][0]
        top_score = result["scores"][0]

        category_slug = self._category_slug_map.get(top_label, "misc")

        return ClassificationResult(
            category_slug=category_slug,
            confidence=top_score,
            all_scores=dict(zip(result["labels"], result["scores"])),
            source="zero_shot_dynamic",
            model_name=self.model_name,
            original_label=top_label,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Embedding-based Classifier
# ─────────────────────────────────────────────────────────────────────────────


class EmbeddingClassifier(ExpenseClassifier):
    """
    Classifier using sentence embeddings and cosine similarity.

    Faster than zero-shot for large-scale classification.
    Requires pre-computed category embeddings.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._loaded = False
        self._category_embeddings: dict[str, list[float]] = {}

    def _load_model(self) -> None:
        """Load sentence transformer model."""
        if self._loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._loaded = True

            # Pre-compute category embeddings using Spanish descriptions
            self._compute_category_embeddings()

        except Exception as e:
            logger.error("failed_to_load_embedding_model", error=str(e))
            raise

    def _compute_category_embeddings(self) -> None:
        """Pre-compute embeddings for category descriptions."""
        category_descriptions = {
            "delivery": "comida para llevar delivery rappi ifood pedidosya",
            "in_house_food": "supermercado mercado groceries compras comida casa cocinar",
            "out_house_food": "restaurante comer afuera almuerzo cena desayuno cafe",
            "lodging": "hotel hostal airbnb hospedaje alojamiento dormir noche",
            "transport": "taxi uber transporte bus metro gasolina parqueo vuelo",
            "tourism": "turismo entretenimiento museo tour excursion actividad",
            "healthcare": "doctor medico farmacia salud medicina hospital clinica",
            "misc": "otros compras tienda ropa electronica",
        }

        for slug, desc in category_descriptions.items():
            embedding = self._model.encode(desc, convert_to_tensor=False)
            self._category_embeddings[slug] = embedding.tolist()

    def is_available(self) -> bool:
        """Check if model is available."""
        if not self._loaded:
            try:
                self._load_model()
            except Exception:
                return False
        return self._model is not None

    async def classify(
        self,
        description: str,
        merchant: str | None = None,
    ) -> ClassificationResult:
        """Classify using embedding similarity."""
        if not self.is_available():
            raise RuntimeError("Embedding model not available")

        import numpy as np

        text = description.strip()
        if merchant:
            text = f"{merchant} {text}"

        # Get embedding for input
        input_embedding = self._model.encode(text, convert_to_tensor=False)

        # Calculate cosine similarity with each category
        scores = {}
        for slug, cat_emb in self._category_embeddings.items():
            similarity = np.dot(input_embedding, cat_emb) / (
                np.linalg.norm(input_embedding) * np.linalg.norm(cat_emb)
            )
            scores[slug] = float(similarity)

        # Get best match
        best_slug = max(scores, key=scores.get)
        best_score = scores[best_slug]

        # Normalize scores to 0-1 range (similarity can be negative)
        min_score = min(scores.values())
        max_score = max(scores.values())
        if max_score > min_score:
            normalized_scores = {
                k: (v - min_score) / (max_score - min_score) for k, v in scores.items()
            }
        else:
            normalized_scores = scores

        return ClassificationResult(
            category_slug=best_slug,
            confidence=normalized_scores[best_slug],
            all_scores=normalized_scores,
            source="embeddings",
            model_name=self.model_name,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory Function
# ─────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_expense_classifier() -> ExpenseClassifier:
    """
    Get the configured expense classifier (singleton).

    Returns classifier based on settings.classifier_type:
    - "zero_shot": HuggingFaceClassifier (recommended)
    - "embeddings": EmbeddingClassifier (faster)

    Returns:
        Configured ExpenseClassifier instance
    """
    classifier_type = getattr(settings, "classifier_type", "zero_shot")

    if classifier_type == "embeddings":
        logger.info("initializing_embedding_classifier")
        return EmbeddingClassifier()
    else:
        logger.info("initializing_zero_shot_classifier")
        return HuggingFaceClassifier()


async def classify_expense_with_fallback(
    description: str,
    merchant: str | None = None,
    llm_category: str | None = None,
    llm_confidence: float = 0.0,
) -> ClassificationResult:
    """
    Classify expense using ML classifier with fallback logic.

    If LLM provided a category with high confidence, returns that.
    Otherwise, uses ML classifier.

    Args:
        description: Expense description
        merchant: Optional merchant name
        llm_category: Category from LLM extraction (if any)
        llm_confidence: Confidence score from LLM

    Returns:
        ClassificationResult with best category
    """
    confidence_threshold = settings.confidence_threshold

    # If LLM is confident enough, use its category
    if llm_category and llm_confidence >= confidence_threshold:
        logger.debug(
            "using_llm_category",
            category=llm_category,
            confidence=llm_confidence,
        )
        return ClassificationResult(
            category_slug=llm_category,
            confidence=llm_confidence,
            source="llm",
            all_scores={llm_category: llm_confidence},
        )

    # Use ML classifier
    try:
        classifier = get_expense_classifier()
        if classifier.is_available():
            ml_result = await classifier.classify(description, merchant)

            # Use ML if it's more confident
            if ml_result.confidence > llm_confidence:
                logger.info(
                    "ml_classifier_improved_category",
                    llm_category=llm_category,
                    llm_confidence=llm_confidence,
                    ml_category=ml_result.category_slug,
                    ml_confidence=ml_result.confidence,
                )
                return ml_result

    except Exception as e:
        logger.warning("ml_classifier_failed", error=str(e))

    # Fall back to LLM category or misc
    return ClassificationResult(
        category_slug=llm_category or "misc",
        confidence=llm_confidence,
        source="llm_fallback",
        all_scores={llm_category or "misc": llm_confidence},
    )

