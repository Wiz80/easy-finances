"""
Text expense extractor using LangChain with structured output.
Extracts expense information from natural language text using LLM.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import settings
from app.logging_config import get_logger
from app.prompts.expense_extraction import (
    EXPENSE_EXTRACTION_PROMPT,
    calculate_confidence_factors,
)
from app.schemas.extraction import ExtractedExpense

logger = get_logger(__name__)


def get_llm_for_extraction() -> BaseChatModel:
    """
    Get configured LLM for expense extraction based on settings.
    
    Returns:
        Configured LangChain chat model
        
    Raises:
        ValueError: If provider is not supported or API key missing
    """
    provider = settings.llm_provider.lower()
    
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        logger.debug("initializing_openai_llm", model="gpt-4o")
        return ChatOpenAI(
            model="gpt-4o",
            api_key=settings.openai_api_key,
            temperature=0.1,  # Low temperature for more deterministic extraction
        )
    
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        logger.debug("initializing_anthropic_llm", model="claude-3-5-sonnet-20241022")
        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.1,
        )
    
    elif provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not configured")
        
        logger.debug("initializing_google_llm", model="gemini-2.0-flash-exp")
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
    
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: openai, anthropic, google"
        )


def extract_expense_from_text(text: str, **kwargs: Any) -> ExtractedExpense:
    """
    Extract structured expense data from natural language text.
    
    Uses LLM with structured output (Pydantic schema) to parse user messages
    about expenses and return validated ExtractedExpense objects.
    
    Args:
        text: Natural language text describing an expense
        **kwargs: Additional context (e.g., user_id, trip_id for logging)
        
    Returns:
        ExtractedExpense: Validated expense data with confidence score
        
    Raises:
        ValueError: If text is empty or extraction fails
        ValidationError: If LLM output doesn't match schema
        
    Example:
        >>> expense = extract_expense_from_text(
        ...     "Gasté 45.50 dólares en comida en Whole Foods con mi tarjeta Visa"
        ... )
        >>> print(f"{expense.amount} {expense.currency} - {expense.description}")
        45.50 USD - comida en Whole Foods
    """
    if not text or not text.strip():
        raise ValueError("Input text cannot be empty")
    
    text = text.strip()
    
    logger.info(
        "extracting_expense_from_text",
        text_length=len(text),
        provider=settings.llm_provider,
        **kwargs,
    )
    
    try:
        # Get configured LLM
        llm = get_llm_for_extraction()
        
        # Create structured output chain
        # with_structured_output ensures the LLM returns data matching our schema
        structured_llm = llm.with_structured_output(ExtractedExpense)
        
        # Create the chain: prompt | llm
        chain = EXPENSE_EXTRACTION_PROMPT | structured_llm
        
        # Invoke the chain
        logger.debug("invoking_llm_chain", text_preview=text[:100])
        extracted = chain.invoke({"text": text})
        
        # Add raw_input to the extracted data
        extracted.raw_input = text
        
        # Calculate and adjust confidence if needed
        confidence_factors = calculate_confidence_factors(extracted.model_dump())
        
        # Weight factors for final confidence
        weights = {
            "amount": 0.30,
            "currency": 0.20,
            "description": 0.20,
            "category": 0.15,
            "method": 0.15,
        }
        
        # Calculate weighted confidence
        calculated_confidence = sum(
            confidence_factors.get(key, 0) * weight
            for key, weight in weights.items()
        )
        
        # Use the higher of LLM confidence or calculated confidence
        # (LLM might be more accurate in assessing ambiguity)
        final_confidence = max(extracted.confidence, calculated_confidence)
        extracted.confidence = min(final_confidence, 1.0)  # Cap at 1.0
        
        logger.info(
            "expense_extracted_successfully",
            amount=float(extracted.amount),
            currency=extracted.currency,
            category=extracted.category_candidate,
            method=extracted.method,
            confidence=extracted.confidence,
            has_merchant=extracted.merchant is not None,
            **kwargs,
        )
        
        return extracted
    
    except Exception as e:
        logger.error(
            "expense_extraction_failed",
            error=str(e),
            error_type=type(e).__name__,
            text_preview=text[:100],
            **kwargs,
            exc_info=True,
        )
        raise


# Alias for convenience
extract = extract_expense_from_text

