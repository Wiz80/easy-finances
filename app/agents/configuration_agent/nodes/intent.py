"""
Intent detection node for Configuration Agent.

Uses LLM to detect user intent and extract entities from messages.
"""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.configuration_agent.state import ConfigurationAgentState
from app.config import settings
from app.logging_config import get_logger
from app.prompts.configuration_agent import INTENT_DETECTION_PROMPT

logger = get_logger(__name__)


def detect_intent_node(state: ConfigurationAgentState) -> ConfigurationAgentState:
    """
    Detect user intent and extract entities using LLM.
    
    This node:
    1. Builds a prompt with message and context
    2. Calls LLM to analyze the message
    3. Parses the response for intent and entities
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with detected_intent and extracted_entities
    """
    message = state.get("message_body", "")
    current_flow = state.get("current_flow", "unknown")
    pending_field = state.get("pending_field")
    onboarding_completed = state.get("onboarding_completed", False)
    
    logger.debug(
        "detect_intent_start",
        request_id=state.get("request_id"),
        message_preview=message[:50] if message else None,
        current_flow=current_flow
    )
    
    # Quick pattern matching for common intents (before LLM call)
    quick_intent = _quick_intent_detection(message, current_flow, pending_field)
    if quick_intent:
        logger.debug(
            "quick_intent_detected",
            intent=quick_intent["intent"],
            entities=quick_intent.get("entities", {})
        )
        return {
            **state,
            "detected_intent": quick_intent["intent"],
            "extracted_entities": quick_intent.get("entities", {}),
        }
    
    try:
        # Build prompt for LLM
        prompt = INTENT_DETECTION_PROMPT.format(
            message=message,
            current_flow=current_flow,
            pending_field=pending_field or "ninguno",
            onboarding_completed=onboarding_completed
        )
        
        # Call LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.openai_api_key,
        )
        
        response = llm.invoke([
            SystemMessage(content="Eres un clasificador de intenciones. Responde SOLO en JSON válido."),
            HumanMessage(content=prompt)
        ])
        
        # Parse JSON response
        result = _parse_llm_response(response.content)
        
        logger.info(
            "intent_detected",
            request_id=state.get("request_id"),
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            entities=list(result.get("entities", {}).keys())
        )
        
        return {
            **state,
            "detected_intent": result.get("intent", "unknown"),
            "extracted_entities": result.get("entities", {}),
        }
        
    except Exception as e:
        logger.error(
            "detect_intent_error",
            request_id=state.get("request_id"),
            error=str(e),
            exc_info=True
        )
        # Fall back to unknown intent
        return {
            **state,
            "detected_intent": "unknown",
            "extracted_entities": {},
        }


def _quick_intent_detection(
    message: str,
    current_flow: str,
    pending_field: str | None
) -> dict | None:
    """
    Quick pattern-based intent detection for common cases.
    
    Returns intent dict or None if LLM should be used.
    """
    message_lower = message.lower().strip()
    
    # Confirmation patterns - check for phrases that contain confirmations
    confirm_words = ["sí", "si", "yes", "s", "y", "ok", "dale", "correcto", "confirmo", "confirmar", "de acuerdo", "está bien", "claro"]
    deny_words = ["no", "cancelar", "cancel", "cambiar", "incorrecto", "mal"]
    
    # Check if message is primarily a confirmation (contains confirm words but not deny words)
    has_confirm = any(word in message_lower for word in confirm_words)
    has_deny = any(word in message_lower for word in deny_words)
    
    # If it's a short message with confirmation words and no deny words, it's a confirm
    if has_confirm and not has_deny and len(message_lower.split()) <= 4:
        return {"intent": "confirm", "entities": {}}
    
    # If it has deny words without confirm words
    if has_deny and not has_confirm:
        return {"intent": "deny", "entities": {}}
    
    # Help patterns
    if message_lower in ["ayuda", "help", "?", "que puedes hacer"]:
        return {"intent": "help", "entities": {}}
    
    # Greeting patterns
    if message_lower in ["hola", "hi", "hello", "buenas", "buenos días", "buenas tardes"]:
        return {"intent": "greeting", "entities": {}}
    
    # Trip creation patterns
    trip_keywords = ["nuevo viaje", "crear viaje", "configurar viaje", "planear viaje"]
    if any(kw in message_lower for kw in trip_keywords):
        return {"intent": "trip_create", "entities": {}}
    
    # Budget patterns
    budget_keywords = ["presupuesto", "budget", "configurar presupuesto"]
    if any(kw in message_lower for kw in budget_keywords):
        return {"intent": "budget_create", "entities": {}}
    
    # Card patterns
    card_keywords = ["agregar tarjeta", "nueva tarjeta", "registrar tarjeta"]
    if any(kw in message_lower for kw in card_keywords):
        return {"intent": "card_add", "entities": {}}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Handle numeric/menu selections (1, 2, 3, etc.)
    # This is the fast path for menu-based inputs - no LLM needed!
    # ─────────────────────────────────────────────────────────────────────────
    from app.agents.configuration_agent.options import (
        CURRENCY_MAP, TIMEZONE_MAP, parse_selection
    )
    
    # Currency selection (number or code)
    if pending_field == "currency":
        selection = parse_selection(message, CURRENCY_MAP)
        if selection:
            return {
                "intent": "onboarding_provide_currency",
                "entities": {"currency": selection}
            }
    
    # Timezone selection (number only)
    if pending_field == "timezone":
        selection = parse_selection(message, TIMEZONE_MAP)
        if selection:
            return {
                "intent": "onboarding_provide_timezone",
                "entities": {"timezone": selection}
            }
    
    # During onboarding, try to extract specific entities
    if current_flow == "onboarding":
        # Check for currency codes (fallback if not from menu)
        currencies = ["usd", "cop", "mxn", "eur", "pen", "clp", "ars", "brl", "gbp"]
        for curr in currencies:
            if curr in message_lower or curr.upper() in message:
                return {
                    "intent": "onboarding_provide_currency",
                    "entities": {"currency": curr.upper()}
                }
        
        # Check for timezone patterns (explicit timezone format)
        timezone_patterns = ["america/", "europe/", "asia/", "gmt", "utc"]
        if any(tz in message_lower for tz in timezone_patterns):
            tz_value = message.strip()
            return {
                "intent": "onboarding_provide_timezone",
                "entities": {"timezone": tz_value}
            }
        
        # Only assume it's a name if pending_field is explicitly "name"
        # Don't assume short messages are names!
        if pending_field == "name":
            # Only accept if it looks like a name (not numbers, not too short)
            if len(message) >= 2 and len(message) < 50 and not message.isdigit():
                # Exclude confirmations and other patterns
                non_name_words = ["sí", "si", "no", "ok", "hola", "ayuda", "help", "cancelar"]
                if message_lower not in non_name_words:
                    return {
                        "intent": "onboarding_provide_name",
                        "entities": {"name": message.strip()}
                    }
    
    # No quick match, use LLM
    return None


def _parse_llm_response(content: str) -> dict:
    """
    Parse LLM JSON response, handling common issues.
    
    Args:
        content: Raw LLM response
        
    Returns:
        Parsed dict with intent and entities
    """
    # Try to extract JSON from response
    try:
        # Direct parse
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find any JSON object
    json_match = re.search(r'\{[^{}]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Return default
    logger.warning("failed_to_parse_llm_response", content_preview=content[:100])
    return {"intent": "unknown", "entities": {}, "confidence": 0.0}

