"""
IVR Flow Processing Module.

This module provides menu-based (IVR-style) flows for user configuration
without requiring LLM calls. It handles:

- User onboarding (name, currency, timezone, country)
- Budget creation
- Trip configuration
- Card registration

Usage:
    from app.flows import IVRProcessor, IVRFlow
    
    processor = IVRProcessor(db)
    response = await processor.process_onboarding(user, "name", "Harrison")
"""

from app.flows.constants import (
    IVRFlow,
    ONBOARDING_STEPS,
    BUDGET_STEPS,
    TRIP_STEPS,
    CARD_STEPS,
    SUPPORTED_CURRENCIES,
    SUPPORTED_COUNTRIES,
    IVR_KEYWORDS,
)
from app.flows.ivr_processor import IVRProcessor, IVRResponse

__all__ = [
    "IVRFlow",
    "IVRProcessor",
    "IVRResponse",
    "ONBOARDING_STEPS",
    "BUDGET_STEPS",
    "TRIP_STEPS",
    "CARD_STEPS",
    "SUPPORTED_CURRENCIES",
    "SUPPORTED_COUNTRIES",
    "IVR_KEYWORDS",
]

