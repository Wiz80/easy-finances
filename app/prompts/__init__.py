"""
Centralized prompts for the Finanzas Personales application.

All LLM prompts should be defined in this module for easy maintenance,
versioning, and potential localization.
"""

from app.prompts.expense_extraction import (
    EXPENSE_EXTRACTION_SYSTEM,
    EXPENSE_EXTRACTION_USER,
    EXPENSE_EXTRACTION_PROMPT,
    CATEGORY_EXAMPLES,
    calculate_confidence_factors,
)
from app.prompts.sql_generation import (
    SQL_GENERATION_SYSTEM,
    SQL_GENERATION_CONTEXT_TEMPLATE,
    DATE_FILTER_PATTERNS,
)
from app.prompts.coach_agent import COACH_SYSTEM_PROMPT, COACH_RESPONSE_TEMPLATE
from app.prompts.configuration_agent import (
    SYSTEM_PROMPT_ONBOARDING,
    SYSTEM_PROMPT_TRIP_SETUP,
    SYSTEM_PROMPT_BUDGET_CONFIG,
    SYSTEM_PROMPT_CARD_SETUP,
    SYSTEM_PROMPT_GENERAL,
    INTENT_DETECTION_PROMPT,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
)
from app.prompts.coordinator import (
    AGENT_ROUTING_SYSTEM,
    AGENT_ROUTING_USER,
    CANCEL_RESPONSE,
    MENU_RESPONSE,
    HELP_RESPONSE,
    STATUS_RESPONSE,
    FALLBACK_RESPONSE,
    ERROR_RESPONSE,
    ONBOARDING_REQUIRED_RESPONSE,
    build_routing_prompt,
    build_intent_change_prompt,
    build_status_response,
)

__all__ = [
    # Expense extraction
    "EXPENSE_EXTRACTION_SYSTEM",
    "EXPENSE_EXTRACTION_USER",
    "EXPENSE_EXTRACTION_PROMPT",
    "CATEGORY_EXAMPLES",
    "calculate_confidence_factors",
    # SQL generation (for VannaService)
    "SQL_GENERATION_SYSTEM",
    "SQL_GENERATION_CONTEXT_TEMPLATE",
    "DATE_FILTER_PATTERNS",
    # Coach Agent
    "COACH_SYSTEM_PROMPT",
    "COACH_RESPONSE_TEMPLATE",
    # Configuration Agent
    "SYSTEM_PROMPT_ONBOARDING",
    "SYSTEM_PROMPT_TRIP_SETUP",
    "SYSTEM_PROMPT_BUDGET_CONFIG",
    "SYSTEM_PROMPT_CARD_SETUP",
    "SYSTEM_PROMPT_GENERAL",
    "INTENT_DETECTION_PROMPT",
    "WELCOME_MESSAGE",
    "HELP_MESSAGE",
    # Coordinator Agent
    "AGENT_ROUTING_SYSTEM",
    "AGENT_ROUTING_USER",
    "CANCEL_RESPONSE",
    "MENU_RESPONSE",
    "HELP_RESPONSE",
    "STATUS_RESPONSE",
    "FALLBACK_RESPONSE",
    "ERROR_RESPONSE",
    "ONBOARDING_REQUIRED_RESPONSE",
    "build_routing_prompt",
    "build_intent_change_prompt",
    "build_status_response",
]

