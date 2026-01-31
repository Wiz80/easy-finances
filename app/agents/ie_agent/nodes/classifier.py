"""
ML Classification node for IE Agent.

This node enhances category classification using ML models when
the LLM's category confidence is below threshold.
"""

from app.agents.ie_agent.state import IEAgentState
from app.config import settings
from app.logging_config import get_logger
from app.services.expense_classifier import (
    ClassificationResult,
    get_expense_classifier,
)

logger = get_logger(__name__)


async def classify_category_node(state: IEAgentState) -> IEAgentState:
    """
    ML classification node: Improve category when LLM confidence is low.

    This node is called after extraction but before storage.
    It uses the ML classifier to improve category accuracy when:
    - LLM category confidence is below threshold
    - Or as a second opinion to validate the LLM category

    Args:
        state: Current agent state with extracted_expense

    Returns:
        Updated state with potentially improved category
    """
    request_id = state.get("request_id", "unknown")

    logger.info(
        "classify_category_node_start",
        request_id=request_id,
        user_id=str(state.get("user_id")),
    )

    extracted = state.get("extracted_expense")
    if not extracted:
        logger.warning(
            "classify_category_node_skip_no_expense",
            request_id=request_id,
        )
        return state

    # Get current category confidence from extraction
    llm_category = extracted.category_candidate
    llm_confidence = getattr(extracted, "category_confidence", extracted.confidence)

    # Check if ML classification should be attempted
    confidence_threshold = settings.confidence_threshold

    if llm_confidence >= confidence_threshold:
        logger.debug(
            "classify_category_node_skip_high_confidence",
            request_id=request_id,
            llm_category=llm_category,
            llm_confidence=llm_confidence,
        )
        # Already confident, no need for ML
        return state

    # Attempt ML classification
    try:
        classifier = get_expense_classifier()

        if not classifier.is_available():
            logger.warning(
                "ml_classifier_not_available",
                request_id=request_id,
            )
            return state

        # Run classification
        ml_result: ClassificationResult = await classifier.classify(
            description=extracted.description,
            merchant=extracted.merchant,
        )

        logger.info(
            "ml_classification_result",
            request_id=request_id,
            llm_category=llm_category,
            llm_confidence=llm_confidence,
            ml_category=ml_result.category_slug,
            ml_confidence=ml_result.confidence,
            ml_source=ml_result.source,
        )

        # Use ML result if it has higher confidence
        if ml_result.confidence > llm_confidence:
            extracted.category_candidate = ml_result.category_slug
            extracted.category_confidence = ml_result.confidence
            extracted.category_source = ml_result.source

            logger.info(
                "category_improved_by_ml",
                request_id=request_id,
                original_category=llm_category,
                new_category=ml_result.category_slug,
                confidence_improvement=ml_result.confidence - llm_confidence,
            )
        else:
            # Keep LLM category but update source info
            extracted.category_confidence = llm_confidence
            extracted.category_source = "llm"

        return {
            **state,
            "extracted_expense": extracted,
        }

    except Exception as e:
        logger.error(
            "ml_classification_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        # On error, continue with LLM category
        return state


def get_classification_route(state: IEAgentState) -> str:
    """
    Routing function to decide if ML classification is needed.

    Args:
        state: Current agent state

    Returns:
        "classify" if ML classification should be attempted
        "skip_classify" if LLM confidence is sufficient
    """
    extracted = state.get("extracted_expense")
    if not extracted:
        return "skip_classify"

    llm_confidence = getattr(extracted, "category_confidence", extracted.confidence)
    confidence_threshold = settings.confidence_threshold

    # Check if classifier is enabled
    classifier_enabled = getattr(settings, "classifier_enabled", True)

    if not classifier_enabled:
        return "skip_classify"

    if llm_confidence < confidence_threshold:
        return "classify"

    return "skip_classify"

