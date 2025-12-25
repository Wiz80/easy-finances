"""
Response generation node for Configuration Agent.

Uses LLM to generate natural, conversational responses.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.configuration_agent.state import ConfigurationAgentState
from app.config import settings
from app.logging_config import get_logger
from app.prompts.configuration_agent import (
    ERROR_MESSAGE,
    HELP_MESSAGE,
    ONBOARDING_COMPLETE_MESSAGE,
    RESPONSE_GENERATION_PROMPT,
    SYSTEM_PROMPT_BUDGET_CONFIG,
    SYSTEM_PROMPT_CARD_SETUP,
    SYSTEM_PROMPT_GENERAL,
    SYSTEM_PROMPT_ONBOARDING,
    SYSTEM_PROMPT_TRIP_SETUP,
    TRIP_CREATED_MESSAGE,
    WELCOME_MESSAGE,
)

logger = get_logger(__name__)


def generate_response_node(state: ConfigurationAgentState) -> ConfigurationAgentState:
    """
    Generate a conversational response using LLM.
    
    This node:
    1. Checks if a response was already set by processor
    2. Selects appropriate system prompt based on flow
    3. Calls LLM to generate natural response
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with response_text
    """
    # If response already set by processor, use it
    if state.get("response_text"):
        return state
    
    # Check for special cases that have templates
    response = _check_template_responses(state)
    if response:
        return {**state, "response_text": response}
    
    # Generate response using LLM
    try:
        response = _generate_llm_response(state)
        return {**state, "response_text": response}
    except Exception as e:
        logger.error(
            "generate_response_error",
            request_id=state.get("request_id"),
            error=str(e),
            exc_info=True
        )
        return {
            **state,
            "response_text": ERROR_MESSAGE.format(
                error_text="No pude generar una respuesta. Por favor intenta de nuevo."
            ),
        }


def _check_template_responses(state: ConfigurationAgentState) -> str | None:
    """Check if we should use a template response instead of LLM."""
    from app.agents.configuration_agent.options import (
        get_currency_menu,
        get_timezone_menu,
    )
    
    current_flow = state.get("current_flow")
    pending_field = state.get("pending_field")
    intent = state.get("detected_intent")
    flow_data = state.get("flow_data", {})
    persist_type = state.get("persist_type")
    
    # Welcome message for new users
    if current_flow == "onboarding" and pending_field == "name" and intent in ["greeting", None]:
        name_part = f", {state.get('profile_name')}" if state.get("profile_name") else ""
        return WELCOME_MESSAGE.format(name_part=name_part)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Menu-based selections (no LLM needed!)
    # ─────────────────────────────────────────────────────────────────────────
    
    # Currency selection menu
    if pending_field == "currency":
        name = flow_data.get("name", state.get("user_name", "Usuario"))
        return f"¡Perfecto, {name}! 👋\n\n{get_currency_menu()}"
    
    # Timezone selection menu
    if pending_field == "timezone":
        currency = flow_data.get("currency", "USD")
        return f"✅ Moneda configurada: *{currency}*\n\n{get_timezone_menu()}"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Completion messages
    # ─────────────────────────────────────────────────────────────────────────
    
    # Onboarding complete
    if persist_type == "user_complete_onboarding":
        return ONBOARDING_COMPLETE_MESSAGE.format(
            name=flow_data.get("name", state.get("user_name", "Usuario")),
            currency=flow_data.get("currency", state.get("home_currency", "USD")),
            timezone=flow_data.get("timezone", state.get("timezone", "UTC")),
        )
    
    # Trip created
    if persist_type == "trip_create":
        return TRIP_CREATED_MESSAGE.format(
            name=flow_data.get("name", "Viaje"),
            start_date=flow_data.get("start_date", "?"),
            end_date=flow_data.get("end_date", "?"),
            country=flow_data.get("country", "?"),
            city=flow_data.get("city", ""),
            currency=flow_data.get("currency", "USD"),
        )
    
    # Help request
    if intent == "help":
        return HELP_MESSAGE
    
    return None


def _generate_llm_response(state: ConfigurationAgentState) -> str:
    """Generate response using LLM."""
    current_flow = state.get("current_flow", "general")
    
    # Select system prompt based on flow
    system_prompts = {
        "onboarding": SYSTEM_PROMPT_ONBOARDING,
        "trip_setup": SYSTEM_PROMPT_TRIP_SETUP,
        "budget_config": SYSTEM_PROMPT_BUDGET_CONFIG,
        "card_setup": SYSTEM_PROMPT_CARD_SETUP,
        "general": SYSTEM_PROMPT_GENERAL,
    }
    system_prompt = system_prompts.get(current_flow, SYSTEM_PROMPT_GENERAL)
    
    # Build conversation context
    flow_data = state.get("flow_data", {})
    
    # Build the generation prompt
    prompt = RESPONSE_GENERATION_PROMPT.format(
        user_name=state.get("user_name") or state.get("profile_name") or "Usuario",
        current_flow=current_flow,
        flow_data=flow_data,
        detected_intent=state.get("detected_intent", "unknown"),
        extracted_entities=state.get("extracted_entities", {}),
        pending_field=state.get("pending_field") or "ninguno",
        conversation_history=_format_conversation_history(state),
        message=state.get("message_body", ""),
    )
    
    # Call LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,  # Slightly creative for natural responses
        api_key=settings.openai_api_key,
        max_tokens=500,
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])
    
    # Clean up response
    text = response.content.strip()
    
    # Remove any markdown formatting that might have been added
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    
    logger.debug(
        "llm_response_generated",
        request_id=state.get("request_id"),
        response_length=len(text)
    )
    
    return text


def _format_conversation_history(state: ConfigurationAgentState) -> str:
    """Format conversation history for the prompt."""
    messages = state.get("messages", [])
    
    if not messages:
        return "(Sin historial previo)"
    
    # Take last 5 messages for context
    recent = messages[-5:]
    
    formatted = []
    for msg in recent:
        role = "Usuario" if msg.get("role") == "user" else "Asistente"
        content = msg.get("content", "")[:200]  # Truncate long messages
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)

