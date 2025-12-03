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
from app.prompts.sql_generation import SQL_GENERATION_SYSTEM
from app.prompts.coach_agent import COACH_SYSTEM_PROMPT, COACH_RESPONSE_TEMPLATE

__all__ = [
    # Expense extraction
    "EXPENSE_EXTRACTION_SYSTEM",
    "EXPENSE_EXTRACTION_USER",
    "EXPENSE_EXTRACTION_PROMPT",
    "CATEGORY_EXAMPLES",
    "calculate_confidence_factors",
    # SQL generation (for MCP server)
    "SQL_GENERATION_SYSTEM",
    # Coach Agent
    "COACH_SYSTEM_PROMPT",
    "COACH_RESPONSE_TEMPLATE",
]

